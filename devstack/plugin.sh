function spp_pre_install(){
    OFFLINE=$(trueorfalse False OFFLINE)

    if [ "$OFFLINE" != True ]; then
        if is_ubuntu; then
            echo "TODO: install packages necessary for DPDK build"
            sudo apt-get install -y libnuma-dev
            #NOTE(oda): it is environment dependent.
        fi
        #TODO: other OS support (ex. CentOS)
    fi
}

function clone_spp_dpdk(){
    OFFLINE=$(trueorfalse False OFFLINE)
    RECLONE=$(trueorfalse False RECLONE)

    if [[ "$OFFLINE" != True ]]; then
        if [ ! -d "${DPDK_DIR}" ] || [ "$RECLONE" == True ]; then
            git_clone ${DPDK_GIT_REPO} ${DPDK_DIR} ${DPDK_GIT_TAG}
        fi
        if [ ! -d "${SPP_DIR}" ] || [ "$RECLONE" == True ]; then
            git_clone ${SPP_GIT_REPO} ${SPP_DIR} ${SPP_GIT_TAG}
        fi
    fi
}

function build_spp_dpdk(){
    if [[ "$SPP_DPDK_BUILD_SKIP" != True ]]; then
        pushd ${DPDK_DIR}
        sudo make config T=${RTE_TARGET}
        if [ -e "${RTE_TARGET}" ]; then
           rm -rf $RTE_TARGET
        fi
        ln -s -f build ${RTE_TARGET}
        sudo make
        cd ${SPP_DIR}
        sudo SPP_HOME=${SPP_DIR} RTE_TARGET=${RTE_TARGET} RTE_SDK=${RTE_SDK} make
        popd
    fi
}

function free_hugepages(){
    HUGEPAGE_SIZE=$(grep Hugepagesize /proc/meminfo | awk '{ print $2 }')

    sudo rm -rf ${SPP_HUGEPAGE_MOUNT}/rtemap*
    sudo umount ${SPP_HUGEPAGE_MOUNT}

    if [ $SPP_ALLOCATE_HUGEPAGES == 'True' ]; then
       for d in /sys/devices/system/node/node? ; do
          echo 0 | sudo tee $d/hugepages/hugepages-${HUGEPAGE_SIZE}kB/nr_hugepages
       done
    fi
}

function alloc_hugepages(){
    HUGEPAGE_SIZE=$(grep Hugepagesize /proc/meminfo | awk '{ print $2 }')

    if [ $SPP_NUM_HUGEPAGES -eq 0 ]; then
        die 6 $LINENO "SPP_NUM_HUGEPAGES not set"
    fi

    if grep -ws $SPP_HUGEPAGE_MOUNT /proc/mounts > /dev/null; then
        free_hugepages
    fi

    if [ $SPP_ALLOCATE_HUGEPAGES == 'True' ]; then
        for d in /sys/devices/system/node/node? ; do
            echo $SPP_NUM_HUGEPAGES | sudo tee $d/hugepages/hugepages-${HUGEPAGE_SIZE}kB/nr_hugepages
        done
    fi

    sudo mkdir -p $SPP_HUGEPAGE_MOUNT
    sudo mount -t hugetlbfs nodev $SPP_HUGEPAGE_MOUNT

    #TODO: restart libvirtd ?
}

function bind_nics() {
    if [ -n "$DPDK_PORT_MAPPINGS" ]; then
        sudo modprobe uio
        if ! lsmod | grep -ws igb_uio > /dev/null; then
            sudo insmod $DPDK_DIR/build/kmod/igb_uio.ko
        fi

        MAPPINGS=${DPDK_PORT_MAPPINGS//,/ }
        ARRAY=( $MAPPINGS )
        NICS=""
        for pair in "${ARRAY[@]}"; do
            addr=`echo $pair | cut -f 1 -d "#"`
            NICS="$NICS $addr"
        done
        sudo $DPDK_DIR/usertools/dpdk-devbind.py -b igb_uio $NICS
    fi
}

function unbind_nic() {
    pci=$1

    out=$(lspci -s $pci -k | grep 'Kernel modules:')
    driver=${out##*:}
    if [ -n "$driver" ]; then
        sudo $DPDK_DIR/usertools/dpdk-devbind.py -b $driver $pci
    else
        sudo $DPDK_DIR/usertools/dpdk-devbind.py --force -u $pci
    fi
}

function unbind_nics() {
    if [ -n "$DPDK_PORT_MAPPINGS" ]; then
        MAPPINGS=${DPDK_PORT_MAPPINGS//,/ }
        ARRAY=( $MAPPINGS )
        for pair in "${ARRAY[@]}"; do
            addr=`echo $pair | cut -f 1 -d "#"`
            unbind_nic $addr
        done
    fi
}

function prepare_spp_dpdk(){
    alloc_hugepages
    bind_nics
}

function cleanup_spp_dpdk(){
    unbind_nics
    if grep -ws $SPP_HUGEPAGE_MOUNT /proc/mounts > /dev/null; then
        free_hugepages
    fi
}

function configure_etcd() {
    iniset /$Q_PLUGIN_CONF_FILE spp etcd_host $ETCD_HOST
    iniset /$Q_PLUGIN_CONF_FILE spp etcd_port $ETCD_PORT
}

function configure_spp_agent() {
    if [ -n "$SPP_PRIMATY_SOCK_PORT" ]; then
        iniset /$Q_PLUGIN_CONF_FILE spp primary_sock_port $SPP_PRIMATY_SOCK_PORT
    fi
    if [ -n "$SPP_SECONDARY_SOCK_PORT" ]; then
        iniset /$Q_PLUGIN_CONF_FILE spp secondary_sock_port $SPP_SECONDARY_SOCK_PORT
    fi

    if [ -z "$SPP_HOST" ]; then
        SPP_HOST=$(hostname -s)
    fi
    python $NETWORKING_SPP_DIR/devstack/spp-config-build.py \
        $DPDK_PORT_MAPPINGS $SPP_HOST $ETCD_HOST $ETCD_PORT
}

function unconfigure_spp_agent() {
    if [ -z "$SPP_HOST" ]; then
        SPP_HOST=$(hostname -s)
    fi
    python $NETWORKING_SPP_DIR/devstack/spp-config-destroy.py \
        $SPP_HOST $ETCD_HOST $ETCD_PORT
}

function build_spp_primary_service() {
    local service="spp_primary.service"
    local unitfile="$SYSTEMD_DIR/$service"

    MAPPINGS=${DPDK_PORT_MAPPINGS//,/ }
    ARRAY=( $MAPPINGS )
    NUM_VHOST=0
    for map in "${ARRAY[@]}"; do
        num=`echo $map | cut -f 3 -d "#"`
        NUM_VHOST=$(( $NUM_VHOST + $num ))
    done

    PORT_MASK=0
    for ((i=0; i<${#ARRAY[@]}; i++)); do
        PORT_MASK=$(( $PORT_MASK + (1 << $i) ))
    done
    NUM_RING=$(( $NUM_VHOST * 2 ))

    PRIMARY_BIN=$SPP_DIR/src/primary/x86_64-native-linuxapp-gcc/spp_primary
    PRIMARY_CMD="$PRIMARY_BIN -c $SPP_PRIMARY_CORE_MASK -n 4 --socket-mem $SPP_PRIMARY_SOCKET_MEM --huge-dir $SPP_HUGEPAGE_MOUNT --proc-type primary -- -p $PORT_MASK -n $NUM_RING -s 127.0.0.1:$SPP_PRIMATY_SOCK_PORT"

    iniset -sudo $unitfile "Unit" "Description" "Devstack $service"
    iniset -sudo $unitfile "Service" "User" "root"
    iniset -sudo $unitfile "Service" "ExecStart" "$PRIMARY_CMD"
}

function build_spp_vf_service() {
    local sec_id=$1
    local core_mask=$2
    local service="spp_vf-$sec_id.service"
    local unitfile="$SYSTEMD_DIR/$service"

    SEC_BIN=$SPP_DIR/src/vf/x86_64-native-linuxapp-gcc/spp_vf
    SEC_CMD="$SEC_BIN -c $core_mask -n 4 --proc-type secondary -- --client-id $sec_id -s 127.0.0.1:$SPP_SECONDARY_SOCK_PORT --vhost-client"

    iniset -sudo $unitfile "Unit" "Description" "Devstack $service"
    iniset -sudo $unitfile "Service" "User" "root"
    iniset -sudo $unitfile "Service" "ExecStart" "$SEC_CMD"
}

function build_systemd_services() {
    mkdir -p $SYSTEMD_DIR
    build_spp_primary_service
    SEC_ID=1
    MAPPINGS=${DPDK_PORT_MAPPINGS//,/ }
    ARRAY=( $MAPPINGS )
    for map in "${ARRAY[@]}"; do
        mask=`echo $map | cut -f 4 -d "#"`
        build_spp_vf_service $SEC_ID $mask
        SEC_ID=$(( $SEC_ID + 1 ))
    done

    # changes to existing units sometimes need a refresh
    $SYSTEMCTL daemon-reload
    $SYSTEMCTL enable spp_primary.service
    for ((i=1; i<=${#ARRAY[@]}; i++)); do
        $SYSTEMCTL enable spp_vf-$i.service
    done
}

function stop_systemd_services() {
    stop_process q-spp-agt
    MAPPINGS=${DPDK_PORT_MAPPINGS//,/ }
    ARRAY=( $MAPPINGS )
    for ((i=1; i<=${#ARRAY[@]}; i++)); do
        $SYSTEMCTL stop spp_vf-$i.service
    done
    $SYSTEMCTL stop spp_primary.service
}

function prepare_tempest() {
    # NOTE: DEFALUT_IMAGE_NAME must be specified in local.conf explicitly.
    openstack flavor create "$DEFAULT_INSTANCE_TYPE" --ram 4096 --disk 20 --vcpus 2 --public --property hw:mem_page_size=large

    if [ ! -e "$NETWORKING_SPP_DIR/devstack/image/image.qcow2" ]; then
        $NETWORKING_SPP_DIR/devstack/image/build_image.sh $NETWORKING_SPP_DIR
    fi

    openstack --os-cloud=devstack-admin --os-region-name="$REGION_NAME" image create "$DEFAULT_IMAGE_NAME" --public --container-format bare --disk-format qcow2 < $NETWORKING_SPP_DIR/devstack/image/image.qcow2
}

if [[ "$1" == "stack" ]]; then
    case "$2" in
        pre-install)
            if [ "$SPP_MODE" != "controller" ]; then
                spp_pre_install
                clone_spp_dpdk
            fi
            ;;
        install)
            if [ "$SPP_MODE" != "controller" ]; then
                build_spp_dpdk
            fi
            pushd $NETWORKING_SPP_DIR
            sudo python setup.py install
            popd
            if [ "$SPP_MODE" != "controller" ]; then
                prepare_spp_dpdk
            fi
            ;;
        post-config)
            if [ "$SPP_MODE" != "controller" ]; then
                configure_spp_agent
            fi
            configure_etcd
            ;;
        extra)
            if [ "$SPP_MODE" != "controller" ]; then
                build_systemd_services
                # start spp-agent
                # spp services will start from spp-agent.
                run_process q-spp-agt "$SPP_AGENT_BINARY --config-file $NEUTRON_CONF --config-file /$Q_PLUGIN_CONF_FILE"
            fi
            if [ "$SPP_MODE" == "controller" ]; then
                if is_service_enabled tempest; then
                    prepare_tempest
                fi
            fi
            ;;
    esac
elif [[ "$1" == "unstack" ]]; then
    if [ "$SPP_MODE" != "controller" ]; then
        stop_systemd_services
        cleanup_spp_dpdk
        unconfigure_spp_agent
        #TODO: more cleanup ?
    fi
fi
