/*-
 *   BSD LICENSE
 *
 *   Copyright(c) 2018 NTT. All rights reserved.
 *   All rights reserved.
 *
 *   Redistribution and use in source and binary forms, with or without
 *   modification, are permitted provided that the following conditions
 *   are met:
 *
 *     * Redistributions of source code must retain the above copyright
 *       notice, this list of conditions and the following disclaimer.
 *     * Redistributions in binary form must reproduce the above copyright
 *       notice, this list of conditions and the following disclaimer in
 *       the documentation and/or other materials provided with the
 *       distribution.
 *     * Neither the name of Intel Corporation nor the names of its
 *       contributors may be used to endorse or promote products derived
 *       from this software without specific prior written permission.
 *
 *   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 *   A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 *   OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 *   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 *   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 *   DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 *   THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 *   (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 *   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <getopt.h>
#include <signal.h>
#include <stdint.h>
#include <inttypes.h>
#include <unistd.h>
#include <stdio.h>
#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_ether.h>
#include <rte_cycles.h>
#include <rte_lcore.h>
#include <rte_mbuf.h>

#define RX_RING_SIZE 128
#define TX_RING_SIZE 512

#define NUM_MBUFS 8191
#define MBUF_CACHE_SIZE 250
#define BURST_SIZE 32

#define ETHER_TYPE_PING 0x8001

#define MODE_PING 0
#define MODE_PONG 1

static int mode = MODE_PING;
static int debug = 0;
static volatile int force_quit;

static uint16_t nb_ports;
static struct rte_mempool *mbuf_pool;

static const struct rte_eth_conf port_conf_default = {
	.rxmode = { .max_rx_pkt_len = ETHER_MAX_LEN }
};

struct port_info {
	struct ether_addr self_addr;
	struct ether_addr peer_addr;
	unsigned int num_send_cnt;
	unsigned int num_send_pkt;
	unsigned int num_recv_cnt;
	unsigned int num_recv_pkt;
	int peer_detected;
	int send_end;
	int done;
};

static struct port_info port_info[RTE_MAX_ETHPORTS];

static struct option lopts[] = {
	{"ping", no_argument, &mode, MODE_PING},
	{"pong", no_argument, &mode, MODE_PONG},
	{"debug", no_argument, &debug, 1},
	{NULL, 0, 0, 0}
};

static int
parse_args(int argc, char *argv[])
{
	int c;

	while ((c = getopt_long(argc, argv, "", lopts, NULL)) != -1) {
		switch (c) {
		case 0:
			/* long option */
			break;
		default:
			/* invalid option */
			return -1;
		}
	}

	return 0;
}

static
void print_pkt(uint16_t portid, struct ether_hdr *eth, int dir)
{
        char src_mac[ETHER_ADDR_FMT_SIZE];
        char dst_mac[ETHER_ADDR_FMT_SIZE];
	const char *dir_str;

	if (!debug) {
		return;
	}

	ether_format_addr(src_mac, sizeof(src_mac), &eth->s_addr);
	ether_format_addr(dst_mac, sizeof(dst_mac), &eth->d_addr);

        dir_str = dir ? "r " : " s";

	printf("Port %u: %s %s/%s %x\n", (unsigned)portid, dir_str,
		src_mac, dst_mac, eth->ether_type);
}

static int
send_pkt(uint16_t portid)
{
	struct port_info *pi = &port_info[portid];
	struct ether_hdr *eth;
        struct rte_mbuf *m;
	uint16_t nb_tx;

	m = rte_pktmbuf_alloc(mbuf_pool);
        if (m == NULL) {
		printf("rte_pktmbuf_alloc error\n");
		return 0;
	}
	eth = rte_pktmbuf_mtod(m, struct ether_hdr *);
	ether_addr_copy(&pi->self_addr, &eth->s_addr);
	ether_addr_copy(&pi->peer_addr, &eth->d_addr);
	eth->ether_type = rte_cpu_to_be_16(ETHER_TYPE_PING);
	m->pkt_len = 60;
	m->data_len = 60;

	nb_tx = rte_eth_tx_burst(portid, 0, &m, 1);
	rte_pktmbuf_free(m);

	if (nb_tx == 1) {
		print_pkt(portid, eth, 0);
		return 1;
	} else {
		return 0;
	}
}

static void
send_ping(uint16_t portid)
{
	struct port_info *pi = &port_info[portid];
	int ret;

	if (pi->send_end) {
		return;
	}
	ret = send_pkt(portid);
	if (ret) {
		pi->num_send_cnt++;
		pi->num_send_pkt++;
		if (pi->peer_detected) {
			pi->send_end = 1;
			pi->done = 1;
		} else {
			(void)sleep(1);
		}
	}
}

static void
send_pong(uint16_t portid)
{
	struct port_info *pi = &port_info[portid];
	int ret;

	if (!pi->peer_detected || pi->send_end) {
		return;
	}
	ret = send_pkt(portid);
	if (ret) {
		pi->num_send_cnt++;
		pi->num_send_pkt++;
		pi->send_end = 1;
	}
}

static int
is_bcast(struct ether_addr *addr)
{
	int i;

	for (i = 0; i < ETHER_ADDR_LEN; i++) {
		if (addr->addr_bytes[i] != 0xff) {
			return 0;
		}
	}

	return 1;
}

static int
is_same_mac(struct ether_addr *addr1, struct ether_addr *addr2)
{
	int i;

	for (i = 0; i < ETHER_ADDR_LEN; i++) {
		if (addr1->addr_bytes[i] != addr2->addr_bytes[i]) {
			return 0;
		}
	}

	return 1;
}

static
void do_ping_pong(uint16_t portid)
{
	struct port_info *pi = &port_info[portid];
	struct rte_mbuf *bufs[BURST_SIZE];
	uint16_t nb_rx;
	struct ether_hdr *eth;
        char mac[ETHER_ADDR_FMT_SIZE];
	int i;

	if (mode == MODE_PING) {
		send_ping(portid);
	} else {
		send_pong(portid);
	}

	nb_rx = rte_eth_rx_burst(portid, 0, bufs, BURST_SIZE);
	if (nb_rx == 0) {
		return;
	}
	pi->num_recv_cnt++;
	pi->num_recv_pkt += nb_rx;

	for (i = 0; i < nb_rx; i++) {
		eth = rte_pktmbuf_mtod(bufs[i], struct ether_hdr *);
		print_pkt(portid, eth, 1);
		if (eth->ether_type != rte_cpu_to_be_16(ETHER_TYPE_PING)) {
			printf("Port %u: unknown type recieved\n", (unsigned)portid);
			continue;
		}
		if (!pi->peer_detected) {
			if (mode == MODE_PONG) {
				if (!is_bcast(&eth->d_addr)) {
					printf("Port %u: inconsistent. should be broad cast.\n", (unsigned)portid);
					continue;
				}
			} else {
				if (!is_same_mac(&eth->d_addr, &pi->self_addr)) {
					printf("Port %u: inconsistent. should be my mac.\n", (unsigned)portid);
					continue;
				}
			}
			ether_addr_copy(&eth->s_addr, &pi->peer_addr);
			pi->peer_detected = 1;
			ether_format_addr(mac, sizeof(mac), &eth->s_addr);
			printf("Port %u peer MAC: %s\n", (unsigned)portid, mac);
		} if (mode == MODE_PONG) {
			if (is_same_mac(&eth->d_addr, &pi->self_addr)) {
				pi->done = 1;
			} else if (!is_bcast(&eth->d_addr)) {
				printf("Port %u: inconsistent. should be broad cast.\n", (unsigned)portid);
			}
		}
	}

	for (i = 0; i < nb_rx; i++) {
		rte_pktmbuf_free(bufs[i]);
	}
}

static int is_all_done(void)
{
	uint16_t portid;

	for (portid = 0; portid < nb_ports; portid++) {
		if (port_info[portid].done == 0) {
			return 0;
		}
	}
	return 1;
}

static int
lcore_main(void)
{
	uint16_t portid;

	while (!force_quit) {
		for (portid = 0; portid < nb_ports; portid++) {
			if (!port_info[portid].done) {
				do_ping_pong(portid);
			}
		}
		if (is_all_done()) {
			return 1;
		}
	}

	return 0;
}

static void
signal_handler(int signum)
{
	printf("signel %d recieved\n", signum);
	force_quit = 1;
}

int
main(int argc, char *argv[])
{
	int ret;
	uint16_t portid;
	struct rte_eth_conf port_conf = port_conf_default;
	struct ether_addr *addr;
        char mac[ETHER_ADDR_FMT_SIZE];
	int i;

	ret = rte_eal_init(argc, argv);
	if (ret < 0) {
		rte_exit(EXIT_FAILURE, "EAL initialization failed\n");
	}
	argc -= ret;
	argv += ret;

	ret = parse_args(argc, argv);
	if (ret < 0) {
		rte_exit(EXIT_FAILURE, "Invalid option\n");
	}

	nb_ports = rte_eth_dev_count();
	if (nb_ports == 0) {
		rte_exit(EXIT_FAILURE, "No Ethernet ports\n");
	}

	mbuf_pool = rte_pktmbuf_pool_create("MBUF_POOL", NUM_MBUFS * nb_ports,
		MBUF_CACHE_SIZE, 0, RTE_MBUF_DEFAULT_BUF_SIZE, rte_socket_id());

	if (mbuf_pool == NULL) {
		rte_exit(EXIT_FAILURE, "Cannot create mbuf pool\n");
	}

	for (portid = 0; portid < nb_ports; portid++) {
		ret = rte_eth_dev_configure(portid, 1, 1, &port_conf);
		if (ret != 0) {
			rte_exit(EXIT_FAILURE, "rte_eth_dev_configure failed\n");
		}

		ret = rte_eth_rx_queue_setup(portid, 0, RX_RING_SIZE,
			rte_eth_dev_socket_id(portid), NULL, mbuf_pool);
		if (ret < 0) {
			rte_exit(EXIT_FAILURE, "rte_eth_rx_queue_setup failed\n");
		}

		ret = rte_eth_tx_queue_setup(portid, 0, TX_RING_SIZE,
				rte_eth_dev_socket_id(portid), NULL);
		if (ret < 0) {
			rte_exit(EXIT_FAILURE, "rte_eth_tx_queue_setup failed\n");
		}

		ret = rte_eth_dev_start(portid);
		if (ret < 0) {
			rte_exit(EXIT_FAILURE, "rte_eth_dev_start failed\n");
		}

		/* get self ether addr */
		addr = &port_info[portid].self_addr;
		rte_eth_macaddr_get(portid, addr);
		ether_format_addr(mac, sizeof(mac), addr);
		printf("Port %u MAC: %s\n", (unsigned)portid, mac);

		/* initialize peer ether addr to broad cast at first */
		for (i = 0; i < ETHER_ADDR_LEN; i++) {
			port_info[portid].peer_addr.addr_bytes[i] = 0xff;
		}

		//rte_eth_promiscuous_enable(portid);
	}

	force_quit = 0;
	signal(SIGINT, signal_handler);
	signal(SIGTERM, signal_handler);

	ret = lcore_main();

	printf("\n");
	for (portid = 0; portid < nb_ports; portid++) {
		rte_eth_dev_stop(portid);
		rte_eth_dev_close(portid);
		printf("Port %u: send_cnt(%u) send_pkt(%u), recv_cnt(%u) recv_pkt(%u)\n",
			(unsigned)portid,
			port_info[portid].num_send_cnt,
			port_info[portid].num_send_pkt,
			port_info[portid].num_recv_cnt,
			port_info[portid].num_recv_pkt);
	}
	if (ret) {
		printf("Success.\n");
	} else {
		printf("Aborted.\n");
	}
	fflush(stdout);

	return 0;
}
