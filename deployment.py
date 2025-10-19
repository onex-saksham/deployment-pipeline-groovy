import json
import os
import paramiko
from scp import SCPClient
import pymysql
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    filename = "deployment.log",
    filemode = "a",
    level = logging.INFO,
    format = "%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger()

def password():
    """Load passwords from a JSON file"""

    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, "passwords.json")
    print(file_path)
    with open(file_path, "r") as f:
        return json.load(f)

def get_config(base_path):
    """Load configurations from a JSON file"""

    file_path = os.path.join(base_path, "initialization_deployment_config.json")
    with open(file_path, "r") as f:
        return json.load(f)
    
def jenkins_cred():
    """Load jenkins credentials from a JSON file"""

    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, "jenkins_cred.json")
    with open(file_path, "r") as f:
        return json.load(f)
def debug_environment():
    """Debug the environment to see differences"""
    import os, subprocess, getpass

    logger.info("=== ENVIRONMENT DEBUG INFO ===")
    logger.info(f"Current user: {getpass.getuser()}")
    logger.info(f"Home directory: {os.path.expanduser('~')}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Python path: {os.sys.executable}")

    # Check if files exist
    files_to_check = [
        'initialization_deployment_config.json',
        'jenkins_cred.json', 
        'passwords.json'
    ]

    for file in files_to_check:
        exists = os.path.exists(file)
        logger.info(f"File {file} exists: {exists}")
        if exists:
            try:
                with open(file, 'r') as f:
                    content = f.read()
                    logger.info(f"File {file} size: {len(content)} bytes")
                    # Log first few lines to verify content
                    lines = content.split('\n')[:3]
                    logger.info(f"File {file} preview: {lines}")
            except Exception as e:
                logger.error(f"Error reading {file}: {e}")

    # Test SSH connection directly
    try:
        logger.info("Testing direct SSH connection...")
        result = subprocess.run([
            'ssh', '-o', 'StrictHostKeyChecking=no',
            'saksham@10.20.3.78', 'echo "SSH test successful"'
        ], capture_output=True, text=True, timeout=10)
        logger.info(f"SSH test result: {result.returncode}, output: {result.stdout}, error: {result.stderr}")
    except Exception as e:
        logger.error(f"SSH test failed: {e}")   
    import subprocess
    import getpass

def ssh_connection(ssh, hostname, username, ssh_path, port):
    try:
        # First try SSH key authentication with paramiko
        ssh.connect(hostname=hostname, username=username, key_filename=ssh_path, port=port)
        logger.info("Connected using password-less connectivity")
        return True
    except Exception as e:
        logger.info(f"SSH key authentication failed: {e}")
        try:
            # Fallback to sshpass for password authentication
            password = jenkins_cred().get(hostname) or jenkins_cred().get(f"{username}@{hostname}")
            if not password:
                logger.error(f"No password found for {hostname} in jenkins_cred.json")
                return False
            
            # Test connection using sshpass
            test_cmd = [
                'sshpass', '-p', password,
                'ssh', '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                '-p', str(port),
                f'{username}@{hostname}',
                'echo "connection_test"'
            ]
            
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("SSH connection verified with sshpass, using paramiko with password")
                # Now connect with paramiko using the verified password
                ssh.connect(hostname=hostname, username=username, password=password, port=port)
                logger.info("Connected using jenkins credentials via paramiko")
                return True
            else:
                logger.error(f"sshpass test failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("SSH connection timed out")
            return False
        except Exception as e:
            logger.error(f"Password authentication failed: {e}")
            return False
        
def run(ssh, cmd):
    """Run commands in shell"""

    host = ssh.get_transport().getpeername()[0]
    logger.debug(f"→ [{host}] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        errmsg = stderr.read().decode().strip()
        logger.error(f"✗ [{host}] `{cmd}` failed: {errmsg}")
    else:
        logger.debug(f"✓ [{host}] `{cmd}` → {exit_status}")

def deploy_zookeeper(config, binary_path, ssh):
    """Deploy Zookeeper"""

    zookeeper = config["zookeeper"]
    if zookeeper["deployment_path"] != "":
        deployment_path = zookeeper["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")

    try:
        for i in range(0, len(zookeeper["node_ip"]), 1):
            logger.info(f"Deploying Zookeeper on: {zookeeper["node_ip"][i]}")
            ssh_connection(ssh, zookeeper["node_ip"][i], config["user"], ssh_path, config["ssh_port"])
            
            run(ssh, f"mkdir -p {deployment_path} && "
                f"mkdir -p {zookeeper["properties"]["storage"]}")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Setups/kafka/kafka.tar.xz", f"{deployment_path}")
            run(ssh, f"cd {deployment_path} && "
                "tar xf kafka.tar.xz")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Configurations/zookeeper/zookeeper.properties", f"{deployment_path}/kafka/config")

            run(ssh, f"cd {deployment_path}/kafka/config && "
                f"sed -i -e 's|__zookeeper_storage__|{zookeeper["properties"]["storage"]}|g' "
                f"-e 's|__zookeeper_client_port__|{zookeeper["ports"]["client"]}|g' "
                "zookeeper.properties")
            run(ssh, f"cd {zookeeper["properties"]["storage"]} && "
                f"echo {i+1} > myid")
            
            for j in range(0, len(zookeeper["node_ip"]), 1):
                zookeeper_connection_string = f"server.{j+1}={zookeeper["node_ip"][j]}:{zookeeper["ports"]["peer_to_peer"]}:{zookeeper["ports"]["leader_election"]}"
                run(ssh, f"cd {deployment_path}/kafka/config && "
                    f"echo {zookeeper_connection_string} >> zookeeper.properties")

            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Services/zookeeper/zookeeper.service", f"{service_path}")
            run(ssh, f"cd {service_path} && "
                f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                "zookeeper.service")
            run(ssh, "systemctl --user daemon-reload && "
                "systemctl --user enable zookeeper.service && "
                "systemctl --user start zookeeper.service")

            logger.info(f"Zookeeper successfully started on: {zookeeper["node_ip"][i]}")
    except Exception as e:
        logger.error(f"Error in deploying Zookeeper: {e}")

def deploy_kafka(config, binary_path, ssh):
    """Deploy Kafka"""

    kafka = config["kafka"]
    if kafka["deployment_path"] != "":
        deployment_path = kafka["deployment_path"]
    else:
        deployment_path = config["deployment_path"]
    deployment_type = config["deployment_type"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")
    jmx_command = f"export KAFKA_OPTS=\"-javaagent:$base_dir/../libs/jmx_prometheus_javaagent.jar={kafka["ports"]["jmx"]}:$base_dir/../config/kafka-jmx-config.yml\""

    zookeeper = config["zookeeper"]
    zookeeper_connection_string = ""
    for i in range(0, len(zookeeper["node_ip"]), 1):
        zookeeper_connection_string += f"{zookeeper["node_ip"][i]}:{zookeeper["ports"]["client"]},"
    zookeeper_connection_string = zookeeper_connection_string[:-1]

    try:
        for i in range(0, len(kafka["broker_ip"]), 1):
            logger.info(f"Deploying Kafka on: {kafka["broker_ip"][i]}")
            ssh_connection(ssh, kafka["broker_ip"][i], config["user"], ssh_path, config["ssh_port"])
            
            run(ssh, f"mkdir -p {deployment_path} && "
                f"mkdir -p {kafka["properties"]["storage"]}")
            if deployment_type == "single" and kafka["broker_ip"][0] == zookeeper["node_ip"][0]:
                pass
            else:
                with SCPClient(ssh.get_transport()) as scp:
                    scp.put(f"{binary_path}/Setups/kafka/kafka.tar.xz", f"{deployment_path}")
                run(ssh, f"cd {deployment_path} && "
                    "tar xf kafka.tar.xz")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Setups/kafka/jmx_prometheus_javaagent.jar", f"{deployment_path}/kafka/libs")
                scp.put(f"{binary_path}/Configurations/kafka/server.properties", f"{deployment_path}/kafka/config")
                scp.put(f"{binary_path}/Configurations/kafka/kafka-jmx-config.yml", f"{deployment_path}/kafka/config")

            run(ssh, f"cd {deployment_path}/kafka/config && "
                f"sed -i -e 's|__kafka_broker_id__|{i}|g' "
                f"-e 's|__kafka_broker_ip__|{kafka["broker_ip"][i]}|g' "
                f"-e 's|__kafka_listener_port__|{kafka["ports"]["listener"]}|g' "
                f"-e 's|__kafka_storage__|{kafka["properties"]["storage"]}|g' "
                f"-e 's|__kafka_num_partitions__|{kafka["properties"]["num_partitions"][deployment_type]}|g' "
                f"-e 's|__kafka_replication_factor__|{kafka["properties"]["replication_factor"][deployment_type]}|g' "
                f"-e 's|__kafka_log_retention_hours__|{kafka["properties"]["log_retention_hours"]}|g' "
                f"-e 's|__zookeeper_connection_string__|{zookeeper_connection_string}|g' "
                "server.properties")
            run(ssh, f"cd {deployment_path}/kafka/bin && "
                f"sed -i -e '/^EXTRA_ARGS=/i {jmx_command}' "
                "kafka-server-start.sh")
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Services/kafka/kafka.service", f"{service_path}")
            run(ssh, f"cd {service_path} && "
                f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                "kafka.service")
            run(ssh, "systemctl --user daemon-reload && "
                "systemctl --user enable kafka.service && "
                "systemctl --user start kafka.service")

            logger.info(f"Kafka successfully started on: {kafka["broker_ip"][i]}")
    except Exception as e:
        logger.error(f"Error in deploying Kafka: {e}")

def deploy_doris_fe(config, binary_path, ssh):
    """Deploy Doris FE"""
    print("Doris fe deploying")
    doris_fe = config["doris_fe"]
    if doris_fe["deployment_path"] != "":
        deployment_path = doris_fe["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")

    try:
        for i in range(0, len(doris_fe["node_ip"]), 1):
            logger.info(f"Deploying Doris FE on: {doris_fe["node_ip"][i]}")
            ssh_connection(ssh, doris_fe["node_ip"][i], config["user"], ssh_path, config["ssh_port"])

            run(ssh, f"mkdir -p {deployment_path}")
            logger.info(f"making {deployment_path}")
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Setups/doris/doris.tar.xz", f"{deployment_path}")
            run(ssh, f"cd {deployment_path} && "
                "tar xf doris.tar.xz")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Configurations/doris_fe/fe.conf", f"{deployment_path}/doris/fe/conf")

            logger.info(f"scp config files for fe done")
            
            
            run(ssh, f"cd {deployment_path}/doris/fe/conf && "
                f"sed -i -e 's|__doris_fe_log__|{doris_fe["properties"]["log"]}|g' "
                f"-e 's|__doris_http_port__|{doris_fe["ports"]["http"]}|g' "
                f"-e 's|__doris_edit_log_port__|{doris_fe["ports"]["edit_log"]}|g' "
                f"-e 's|__doris_rpc_port__|{doris_fe["ports"]["rpc"]}|g' "
                f"-e 's|__doris_query_port__|{doris_fe["ports"]["query"]}|g' "
                "fe.conf")

            if not i:
                with SCPClient(ssh.get_transport()) as scp:
                    scp.put(f"{binary_path}/Services/doris_fe/doris_fe.service", f"{service_path}")
                run(ssh, f"cd {service_path} && "
                    f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                    "doris_fe.service")
                run(ssh, "systemctl --user daemon-reload && "
                    "systemctl --user enable doris_fe.service && "
                    "systemctl --user start doris_fe.service")
                
                logger.info(f"scp fe service and reload with the serice")
            else:
                with SCPClient(ssh.get_transport()) as scp:
                    scp.put(f"{binary_path}/Services/doris_fe/doris_fe_follower.service", f"{service_path}")
                run(ssh, f"cd {service_path} && "
                    f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                    f"-e 's|__doris_fe_master_ip__|{doris_fe["node_ip"][0]}|g' "
                    f"-e 's|__doris_fe_edit_log_port__|{doris_fe["ports"]["edit_log"]}|g' "
                    "doris_fe_follower.service")
                run(ssh, "systemctl --user daemon-reload && "
                    "systemctl --user enable doris_fe_follower.service && "
                    "systemctl --user start doris_fe_follower.service")
                logger.info(f"scp fe service and reload with the serice")
            logger.info(f"Doris FE successfully started on: {doris_fe["node_ip"][i]}")
    except Exception as e:
        logger.error(f"Error in deploying Doris FE: {e}")

def deploy_doris_be(config, binary_path, ssh):
    """Deploy Doris BE"""

    print("Doris be deploying")
    doris_be = config["doris_be"]
    if doris_be["deployment_path"] != "":
        deployment_path = doris_be["deployment_path"]
        print(deployment_path)
    else:
        deployment_path = config["deployment_path"]
    deployment_type = config["deployment_type"]
    print(deployment_type)

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    print(ssh_path)
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")
    doris_fe = config["doris_fe"]
    logger.info(f"trying compeleted config")

    try:
        for i in range(0, len(doris_be["node_ip"]), 1):
            logger.info(f"Deploying Doris BE on: {doris_be["node_ip"][i]}")
            ssh_connection(ssh, doris_be["node_ip"][i], config["user"], ssh_path, config["ssh_port"])

            logger.info(f"Doris be deploying")
            
            run(ssh, f"mkdir -p {deployment_path} && "
                f"mkdir -p {doris_be["properties"]["storage"]}")
            if deployment_type == "single" and doris_be["node_ip"][0] == doris_fe["node_ip"][0]:
                pass
                logger.info(f"SCP tar")
            else:
                with SCPClient(ssh.get_transport()) as scp:
                    scp.put(f"{binary_path}/Setups/doris/doris.tar.xz", f"{deployment_path}")
                run(ssh, f"cd {deployment_path} && "
                    "tar xf doris.tar.xz")
                logger.info("SCP tar for multinode")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Configurations/doris_be/be.conf", f"{deployment_path}/doris/be/conf")

            run(ssh, f"cd {deployment_path}/doris/be/conf && "
                f"sed -i -e 's|__doris_be_log__|{doris_be["properties"]["log"]}|g' "
                f"-e 's|__doris_be_storage__|{doris_be["properties"]["storage"]}|g' "
                f"-e 's|__doris_webserver_port__|{doris_be["ports"]["webserver"]}|g' "
                f"-e 's|__doris_brpc_port__|{doris_be["ports"]["brpc"]}|g' "
                f"-e 's|__doris_heartbeat_service_port__|{doris_be["ports"]["heartbeat_service"]}|g' "
                f"-e 's|__doris_be_port__|{doris_be["ports"]["be"]}|g' "
                "be.conf")

            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Services/doris_be/doris_be.service", f"{service_path}")
            run(ssh, f"cd {service_path} && "
                f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                "doris_be.service")
            run(ssh, "systemctl --user daemon-reload && "
                "systemctl --user enable doris_be.service && "
                "systemctl --user start doris_be.service")

            logger.info(f"Doris BE successfully started on: {doris_be["node_ip"][i]}")
    except Exception as e:
        logger.error(f"Error in deploying Doris BE: {e}")

def connect_doris_fe_and_be(config, binary_path, ssh):
    """Connect Doris FE and BE"""

    logger.info("Connecting Doris FE and BE")
    time.sleep(300)

    print("Doris connect is deploying")
    doris_fe_node_ip = config["doris_fe"]["node_ip"]
    doris_fe_node_port = config["doris_fe"]["ports"]
    doris_be_node_ip = config["doris_be"]["node_ip"]
    doris_be_node_port = config["doris_be"]["ports"]

    conn = pymysql.connect(
        host=doris_fe_node_ip[0],
        user="root",
        password="",
        database="mysql",
        port=doris_fe_node_port["query"]
    )

    try:
        with conn.cursor() as cursor:
            for i in range(1, len(doris_fe_node_ip), 1):
                cursor.execute(f"alter system add follower '{doris_fe_node_ip[i]}:{doris_fe_node_port["edit_log"]}'")
            for i in range(0, len(doris_be_node_ip), 1):
                cursor.execute(f"alter system add backend '{doris_be_node_ip[i]}:{doris_be_node_port["heartbeat_service"]}'")

            cursor.execute(f"alter user 'root'@'%' identified by '{password()["root"]}'")

        logger.info("Doris FE and BE connected")
    except Exception as e:
        logger.error(f"Error in connecting Doris FE and BE: {e}")
    finally:
        conn.close()


def deploy_node_exporter(config, binary_path, ssh):
    """Deploy Node Exporter"""

    node_exporter = config["node_exporter"]
    if node_exporter["deployment_path"] != "":
        deployment_path = node_exporter["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")
    node_exporter_path = os.path.join("/home", config["user"], ".local", "bin")

    tool_ip = []
    for i in range(0, len(node_exporter["for"]), 1):
        tool = node_exporter["for"][i]
        if tool == "kafka":
            ip = config[tool]["broker_ip"]
        else:
            ip = config[tool]["node_ip"]
        if isinstance(ip, list) and ip != [] and ip[0][0] != '_':
            tool_ip += ip
        elif isinstance(ip, str) and ip != "" and ip[0] != '_':
            tool_ip += [ip]
        else:
            pass
    tool_ip = list(set(tool_ip))

    try:
        for i in range(0, len(tool_ip), 1):
            logger.info(f"Deploying Node Exporter on: {tool_ip[i]}")
            ssh_connection(ssh, tool_ip[i], config["user"], ssh_path, config["ssh_port"])

            run(ssh, f"mkdir -p {deployment_path} && "
                f"mkdir -p {node_exporter_path}")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Setups/node_exporter/node_exporter.tar.xz", f"{deployment_path}")
            run(ssh, f"cd {deployment_path} && "
                "tar xf node_exporter.tar.xz")
            run(ssh, f"cd {deployment_path} && "
                f"mv node_exporter {node_exporter_path}")
            
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Services/node_exporter/node_exporter.service", f"{service_path}")
            run(ssh, f"cd {service_path} && "
                f"sed -i -e 's|__deployment_path__|{node_exporter_path}|g' "
                "node_exporter.service")
            run(ssh, "systemctl --user daemon-reload && "
                "systemctl --user enable node_exporter.service && "
                "systemctl --user start node_exporter.service")

            logger.info(f"Node Exporter successfully started on: {tool_ip[i]}")
    except Exception as e:
        logger.error(f"Error in deploying Node Exporter: {e}")

def deploy_kafka_exporter(config, binary_path, ssh):
    """Deploy Kafka Exporter"""

    kafka_exporter = config["kafka_exporter"]
    if kafka_exporter["deployment_path"] != "":
        deployment_path = kafka_exporter["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config['base_user']}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config['user']}", ".config", "systemd", "user")

    kafka = config["kafka"]
    kafka_exporter_string = ""
    for i in range(0, len(kafka["broker_ip"]), 1):
        kafka_exporter_string += f"--kafka.server={kafka["broker_ip"][i]}:{kafka["ports"]["listener"]} "
    kafka_exporter_string = kafka_exporter_string[:-1]

    try:
        for i in range(0, len(kafka["broker_ip"]), 1):
            logger.info(f"Deploying Kafka Exporter on: {kafka["broker_ip"][i]}")
            ssh_connection(ssh, kafka["broker_ip"][i], config["user"], ssh_path, config["ssh_port"])

            run(ssh, f"mkdir -p {deployment_path}")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Setups/kafka_exporter/kafka_exporter.tar.xz", f"{deployment_path}")
            run(ssh, f"cd {deployment_path} && "
                "tar xf kafka_exporter.tar.xz")

            with SCPClient(ssh.get_transport()) as scp:
                scp.put(f"{binary_path}/Services/kafka_exporter/kafka_exporter.service", f"{service_path}")
            run(ssh, f"cd {service_path} && "
                f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                f"-e 's|__kafka_exporter_string__|{kafka_exporter_string}|g' "
                "kafka_exporter.service")
            run(ssh, "systemctl --user daemon-reload && "
                "systemctl --user enable kafka_exporter.service && "
                "systemctl --user start kafka_exporter.service")

            logger.info(f"Kafka Exporter successfully started on: {kafka["broker_ip"][i]}")
    except Exception as e:
        logger.error(f"Failed to deploy Kafka Exporter: {e}")

def deploy_prometheus(config, binary_path, ssh):
    """Deploy Prometheus"""

    monitoring = config["monitoring"]
    if monitoring["deployment_path"] != "":
        deployment_path = monitoring["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")
    node_exporter_port = config["node_exporter"]["ports"]["listener"]

    zookeeper_node_ip = config["zookeeper"]["node_ip"]
    zookeeper_node_exporter = []
    for i in range(0, len(zookeeper_node_ip), 1):
        zookeeper_node_exporter.append(f"{zookeeper_node_ip[i]}:{node_exporter_port}")

    kafka_broker_ip = config["kafka"]["broker_ip"]
    kafka_broker_port = config["kafka"]["ports"]
    kafka_exporter_port = config["kafka_exporter"]["ports"]["listener"]
    kafka_broker = []
    kafka_node_exporter = []
    kafka_exporter = []
    for i in range(0, len(kafka_broker_ip), 1):
        kafka_broker.append(f"{kafka_broker_ip[i]}:{kafka_broker_port["jmx"]}")
        kafka_node_exporter.append(f"{kafka_broker_ip[i]}:{node_exporter_port}")
        kafka_exporter.append(f"{kafka_broker_ip[i]}:{kafka_exporter_port}")

    doris_fe_node_ip = config["doris_fe"]["node_ip"]
    doris_fe_node_port = config["doris_fe"]["ports"]
    doris_fe_node = []
    doris_fe_node_exporter = []
    for i in range(0, len(doris_fe_node_ip), 1):
        doris_fe_node.append(f"{doris_fe_node_ip[i]}:{doris_fe_node_port["http"]}")
        doris_fe_node_exporter.append(f"{doris_fe_node_ip[i]}:{node_exporter_port}")

    doris_be_node_ip = config["doris_be"]["node_ip"]
    doris_be_node_port = config["doris_be"]["ports"]
    doris_be_node = []
    doris_be_node_exporter = []
    for i in range(0, len(doris_be_node_ip), 1):
        doris_be_node.append(f"{doris_be_node_ip[i]}:{doris_be_node_port["webserver"]}")
        doris_be_node_exporter.append(f"{doris_be_node_ip[i]}:{node_exporter_port}")

    monitoring_node_ip = config["monitoring"]["node_ip"]
    monitoring_node_exporter = []
    monitoring_node_exporter.append(f"{monitoring_node_ip}:{node_exporter_port}")

    api_node_ip = config["api"]["node_ip"]
    api_node_exporter = []
    for i in range(0, len(api_node_ip), 1):
        api_node_exporter.append(f"{api_node_ip[i]}:{node_exporter_port}")

    try:
        logger.info(f"Deploying Prometheus on: {monitoring["node_ip"]}")
        ssh_connection(ssh, monitoring["node_ip"], config["user"], ssh_path, config["ssh_port"])

        run(ssh, f"mkdir -p {deployment_path}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Setups/prometheus/prometheus.tar.xz", f"{deployment_path}")
        run(ssh, f"cd {deployment_path} && "
            "tar xf prometheus.tar.xz")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Configurations/prometheus/prometheus.yml", f"{deployment_path}/prometheus")

        run(ssh, f"cd {deployment_path}/prometheus && "
            f"sed -i -e 's|__prometheus_ip__|{monitoring["node_ip"]}|g' "
            f"-e 's|__prometheus_port__|{monitoring["ports"]["prometheus"]}|g' "
            f"-e 's|__kafka_broker__|{kafka_broker}|g' "
            f"-e 's|__doris_fe_node__|{doris_fe_node}|g' "
            f"-e 's|__doris_be_node__|{doris_be_node}|g' "
            f"-e 's|__zookeeper_node_exporter__|{zookeeper_node_exporter}|g' "
            f"-e 's|__kafka_node_exporter__|{kafka_node_exporter}|g' "
            f"-e 's|__kafka_exporter__|{kafka_exporter}|g' "
            f"-e 's|__doris_fe_node_exporter__|{doris_fe_node_exporter}|g' "
            f"-e 's|__doris_be_node_exporter__|{doris_be_node_exporter}|g' "
            f"-e 's|__monitoring_node_exporter__|{monitoring_node_exporter}|g' "
            f"-e 's|__api_node_exporter__|{api_node_exporter}|g' "
            "prometheus.yml")

        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Services/prometheus/prometheus.service", f"{service_path}")
        run(ssh, f"cd {service_path} && "
            f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
            "prometheus.service")
        run(ssh, "systemctl --user daemon-reload && "
            "systemctl --user enable prometheus.service && "
            "systemctl --user start prometheus.service")

        logger.info(f"Prometheus successfully started on: {monitoring["node_ip"]}")
    except Exception as e:
        logger.error(f"Error in deploying Prometheus: {e}")

def deploy_grafana(config, binary_path, ssh):
    """Deploy Grafana"""

    monitoring = config["monitoring"]
    if monitoring["deployment_path"] != "":
        deployment_path = monitoring["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")

    try:
        logger.info(f"Deploying Grafana on: {monitoring["node_ip"]}")
        ssh_connection(ssh, monitoring["node_ip"], config["user"], ssh_path, config["ssh_port"])

        run(ssh, f"mkdir -p {deployment_path} && "
            f"mkdir -p {monitoring["properties"]["storage"]}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Setups/grafana/grafana.tar.xz", f"{deployment_path}")
        run(ssh, f"cd {deployment_path} && "
            "tar xf grafana.tar.xz")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Configurations/grafana/defaults.ini", f"{deployment_path}/grafana/conf")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Configurations/grafana/datasources.yaml", f"{deployment_path}/grafana/conf/provisioning/datasources")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Configurations/grafana/dashboards.yaml", f"{deployment_path}/grafana/conf/provisioning/dashboards")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Dashboards/ODP-Dashboard.json", f"{deployment_path}/grafana/conf/provisioning/dashboards/json")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Dashboards/TA-10.json", f"{deployment_path}/grafana/conf/provisioning/dashboards/json")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Dashboards/API-Dashboards.json", f"{deployment_path}/grafana/conf/provisioning/dashboards/json")

        run(ssh, f"cd {deployment_path}/grafana/conf && "
            f"sed -i -e 's|__grafana_ip__|{monitoring["node_ip"]}|g' "
            f"-e 's|__grafana_port__|{monitoring["ports"]["grafana"]}|g' "
            f"-e 's|__grafana_storage__|{monitoring["properties"]["storage"]}|g' "
            "defaults.ini")
        run(ssh, f"cd {deployment_path}/grafana/conf/provisioning/datasources && "
            f"sed -i -e 's|__prometheus_ip__|{monitoring["node_ip"]}|g' "
            f"-e 's|__prometheus_port__|{monitoring["ports"]["prometheus"]}|g' "
            "datasources.yaml")
        run(ssh, f"cd {deployment_path}/grafana/conf/provisioning/dashboards && "
            f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
            "dashboards.yaml")

        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Services/grafana/grafana.service", f"{service_path}")
        run(ssh, f"cd {service_path} && "
            f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
            "grafana.service")
        run(ssh, "systemctl --user daemon-reload && "
            "systemctl --user enable grafana.service && "
            "systemctl --user start grafana.service")

        logger.info(f"Grafana successfully started on: {monitoring["node_ip"]}")
    except Exception as e:
        logger.error(f"Error in deploying Grafana: {e}")

def deploy_health_reports(config, binary_path, ssh):
    """Deploy Health Reports"""

    monitoring = config["monitoring"]
    if monitoring["deployment_path"] != "":
        deployment_path = monitoring["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    base_path = os.path.dirname(os.path.abspath(__file__))
    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")

    try:
        logger.info(f"Deploying Health Reports on: {monitoring["node_ip"]}")
        ssh_connection(ssh, monitoring["node_ip"], config["user"], ssh_path, config["ssh_port"])

        run(ssh, f"mkdir -p {deployment_path}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Jobs/health_reports", f"{deployment_path}", recursive=True)
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{base_path}/initialization_deployment_config.json", f"{deployment_path}/health_reports")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{base_path}/smtp_config.json", f"{deployment_path}/health_reports")
        run(ssh, f"cd {deployment_path}/health_reports && "
            f"python3 -m venv venv")
        
        run(ssh, f"cd {deployment_path}/health_reports && "
            "bash -c '. venv/bin/activate && pip install -r requirements.txt'")
        cron_cmd = (
            f"0 0,6,12,18 * * * {deployment_path}/health_reports/venv/bin/python "
            f"{deployment_path}/health_reports/health_report.py >> {deployment_path}/health_reports/health_report.log 2>&1"
        )
        run(ssh, f"(crontab -l 2>/dev/null; echo \"{cron_cmd}\") | crontab -")

        logger.info(f"Health Reports successfully started on: {monitoring["node_ip"]}")
    except Exception as e:
        logger.error(f"Error in deploying Health Reports: {e}")

def deploy_recon(config, binary_path, ssh):
    """Deploy Recon"""

    monitoring = config["monitoring"]
    if monitoring["deployment_path"] != "":
        deployment_path = monitoring["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    base_path = os.path.dirname(os.path.abspath(__file__))
    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")

    try:
        logger.info(f"Deploying Recon on: {monitoring["node_ip"]}")
        ssh_connection(ssh, monitoring["node_ip"], config["user"], ssh_path, config["ssh_port"])

        run(ssh, f"mkdir -p {deployment_path}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Jobs/kafka_metadata", f"{deployment_path}", recursive=True)
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Jobs/recon", f"{deployment_path}", recursive=True)
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{base_path}/smtp_config.json", f"{deployment_path}/recon")
        run(ssh, f"cd {deployment_path}/kafka_metadata && "
            f"python3 -m venv venv")
        run(ssh, f"cd {deployment_path}/recon && "
            f"python3 -m venv venv")
        
        run(ssh, f"cd {deployment_path}/kafka_metadata && "
            "bash -c '. venv/bin/activate && pip install -r requirements.txt'")
        run(ssh, f"cd {deployment_path}/recon && "
            "bash -c '. venv/bin/activate && pip install -r requirements.txt'")

        logger.info(f"Recon successfully started on: {monitoring["node_ip"]}")
    except Exception as e:
        logger.error(f"Error in deploying Recon: {e}")

def deploy_jobs(config, binary_path, ssh):
    """Deploy Jobs"""

    backend_job = config["backend_job"]
    if backend_job["deployment_path"] != "":
        deployment_path = backend_job["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    doris_fe_node_ip = config["doris_fe"]["node_ip"]
    doris_fe_node_port = config["doris_fe"]["ports"]

    try:
        logger.info(f"Deploying Jobs on: {backend_job["node_ip"]}")
        ssh_connection(ssh, backend_job["node_ip"], config["user"], ssh_path, config["ssh_port"])

        run(ssh, f"mkdir -p {deployment_path}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Jobs/backend_services", f"{deployment_path}", recursive=True)
        run(ssh, f"cd {deployment_path}/backend_services && "
            f"python3 -m venv venv")
        
        run(ssh, f"cd {deployment_path}/backend_services && "
            f"sed -i -e 's|__doris_fe_master_ip__|{doris_fe_node_ip[0]}|g' "
            f"-e 's|__doris_fe_query_port__|{doris_fe_node_port["query"]}|g' "
            f"-e 's|__user__|doris_write_user|g' "
            f"-e 's|__password__|{password()["doris_write_user"]}|g' "
            f"-e 's|__deployment_path__|{deployment_path}|g' "
            "config.py")
        
        run(ssh, f"cd {deployment_path}/backend_services && "
            "bash -c '. venv/bin/activate && pip install -r requirements.txt'")

        logger.info(f"Jobs successfully started on: {backend_job["node_ip"]}")
    except Exception as e:
        logger.error(f"Error in deploying Jobs: {e}")

def deploy_api(config, binary_path, ssh):
    """Deploy API"""

    api = config["api"]
    if api["deployment_path"] != "":
        deployment_path = api["deployment_path"]
    else:
        deployment_path = config["deployment_path"]

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")
    doris_fe_node_ip = config["doris_fe"]["node_ip"]
    doris_fe_node_port = config["doris_fe"]["ports"]
    ssh_port = config["ssh_port"]

    backend_job_node_ip = config["backend_job"]["node_ip"]
    if config["backend_job"]["deployment_path"] != "":
        backend_job_path = config["backend_job"]["deployment_path"]
    else:
        backend_job_path = config["deployment_path"]
    version = config["api"]["deployment_version"]
    remote_jobs = config["api"]["remote_jobs"]


    # Determine which types to deploy based on config flags
    deploy_types = []
    if config.get("deploy_sms", False):
        deploy_types.append("SMS")
    if config.get("deploy_whatsapp", False) or config.get("deploy_rcs", False):
        deploy_types.append("WHATSAPP_RCS")

    logger.info(f"API deployment types: {deploy_types}")

    use_nginx = config["api"]["use_nginx"]


    if use_nginx == "true":
        # Nginx load balancer
        doris_ip = backend_job_node_ip
        doris_port = config["backend_job"]["ports"]["doris_fe"]
    else:
        # Direct Doris FE master
        doris_ip = doris_fe_node_ip[0]
        doris_port = doris_fe_node_port["query"]
        

    try:
        for deploy_type in deploy_types:
            if deploy_type == "SMS":
                service_file_name = "aurasummary.service"
                env_file_name = "aurasummary.env"
                api_port = api["ports"]["sms"]
            else:  # WHATSAPP_RCS
                service_file_name = "aurasummarywarcs.service"
                env_file_name = "aurasummarywarcs.env"
                api_port = api["ports"]["warcs"]

            env_file_versioned = f"{env_file_name.replace('.env', '')}-{version}.env"
            service_file_versioned = f"{service_file_name.replace('.service', '')}-{version}.service"

            log4j_file_name = "log4j2.xml" if deploy_type == "SMS" else "log4j2warcs.xml"

            for i in range(0, len(api["node_ip"]), 1):
                logger.info(f"Deploying API on: {api["node_ip"][i]}")
                ssh_connection(ssh, api["node_ip"][i], config["user"], ssh_path, config["ssh_port"])

                run(ssh, f"mkdir -p {deployment_path}/api/logs")
                with SCPClient(ssh.get_transport()) as scp:
                    scp.put(f"{binary_path}/Setups/api/{env_file_name}", f"{deployment_path}/api/")
                # Rename env file
                run(ssh, f"cd {deployment_path}/api && mv {env_file_name} {env_file_versioned}")

                if deploy_type == "SMS":
                    run(ssh, f"cd {deployment_path}/api && "
                             f"sed -i -e 's|__doris_fe_master_ip__|{doris_fe_node_ip[0]}|g' "
                             f"-e 's|__doris_fe_query_port__|{doris_fe_node_port['query']}|g' "
                             f"-e 's|__user__|sms_read_user|g' "
                             f"-e 's|__password__|{password()['sms_read_user']}|g' "
                             f"-e 's|__api_port__|{api_port}|g' "
                             f"-e 's|__backend_user__|{config['user']}|g' "
                             f"-e 's|__backend_node_ip__|{backend_job_node_ip}|g' "
                             f"-e 's|__backend_path__|{backend_job_path}|g' "
                             f"-e 's|__deployment_path__|{deployment_path}|g' "
                             f"-e 's|__ssh_port__|{ssh_port}|g' "
                             f"-e 's|__remote_jobs__|{remote_jobs}|g' "
                             f"{env_file_versioned}")
                else:  # WARCS
                    run(ssh, f"cd {deployment_path}/api && "
                             f"sed -i -e 's|__doris_fe_master_ip__|{doris_fe_node_ip[0]}|g' "
                             f"-e 's|__doris_fe_query_port__|{doris_fe_node_port['query']}|g' "
                             f"-e 's|__wa_user__|wa_read_user|g' "
                             f"-e 's|__wa_password__|{password()['wa_read_user']}|g' "
                             f"-e 's|__rcs_user__|rcs_read_user|g' "
                             f"-e 's|__rcs_password__|{password()['rcs_read_user']}|g' "
                             f"-e 's|__api_port__|{api_port}|g' "
                             f"-e 's|__backend_user__|{config['user']}|g' "
                             f"-e 's|__backend_node_ip__|{backend_job_node_ip}|g' "
                             f"-e 's|__backend_path__|{backend_job_path}|g' "
                             f"-e 's|__deployment_path__|{deployment_path}|g' "
                             f"-e 's|__ssh_port__|{ssh_port}|g' "
                             f"-e 's|__remote_jobs__|{remote_jobs}|g' "
                             f"{env_file_versioned}")

                run(ssh, f"cd {deployment_path}/api && "
                              f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                              f"{log4j_file_name}")


                with SCPClient(ssh.get_transport()) as scp:
                    scp.put(f"{binary_path}/Services/api/{service_file_name}", service_path)
                run(ssh, f"cd {service_path} && mv {service_file_name} {service_file_versioned}")


                run(ssh, f"cd {service_path} && "
                              f"sed -i -e 's|__deployment_path__|{deployment_path}|g' "
                              f"-e 's|__deployment_version__|{version}|g' "
                              f"{service_file_versioned}")

                run(ssh, "systemctl --user daemon-reload && "
                         f"systemctl --user enable {service_file_versioned} && "
                         f"systemctl --user start {service_file_versioned}")

                logger.info(f"{deploy_type} API successfully started on: {api['node_ip'][i]}")
    except Exception as e:
        logger.error(f"Error in deploying API: {e}")


def deploy_nginx(config, binary_path, ssh):
    """Deploy Nginx"""

    backend_job = config["backend_job"]
    if backend_job["deployment_path"] != "":
        deployment_path = backend_job["deployment_path"]
    else:
        deployment_path = config["deployment_path"]
    deployment_type = config["deployment_type"]
    if deployment_type == "single":
        return

    ssh_path = os.path.join("/home", f"{config["base_user"]}", ".ssh", "id_rsa")
    service_path = os.path.join("/home", f"{config["user"]}", ".config", "systemd", "user")

    # Deployment flags
    deploy_sms = config.get("deploy_sms", False)
    deploy_whatsapp = config.get("deploy_whatsapp", False)
    deploy_rcs = config.get("deploy_rcs", False)
    try:
        logger.info(f"Deploying Nginx on: {backend_job["node_ip"]}")
        ssh_connection(ssh, backend_job["node_ip"], config["user"], ssh_path, config["ssh_port"])

        run(ssh, f"mkdir -p {deployment_path}")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Setups/nginx/nginx.tar.xz", f"{deployment_path}")
        run(ssh, f"cd {deployment_path} && "
            "tar xf nginx.tar.xz && "
            "mv nginx nginx_setup")
        
        run(ssh, f"cd {deployment_path}/nginx_setup && "
            f"./configure --prefix={deployment_path}/nginx --with-http_ssl_module --with-stream --with-stream_ssl_module --with-http_v2_module --with-http_stub_status_module --without-http_rewrite_module --without-http_gzip_module")
        run(ssh, f"cd {deployment_path}/nginx_setup && "
            "make && make install")
        run(ssh, f"cd {deployment_path}/nginx/conf && "
            "rm nginx.conf")
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Configurations/nginx/nginx.conf", f"{deployment_path}/nginx/conf")

        # Filter nginx tools
        nginx_tools = backend_job["nginx"]
        tools_to_configure = []
        for tool in nginx_tools:
            if tool == "api_sms" and not deploy_sms:
                continue
            if tool == "api_warcs" and not (deploy_whatsapp or deploy_rcs):
                continue
            tools_to_configure.append(tool)

        # Configure upstream + port replacements
        for tool in tools_to_configure:
            if tool == "doris_fe":
                tool_ip = config[tool]["node_ip"]
                tool_port = config[tool]["ports"]["query"]
                nginx_port = backend_job["ports"]["doris_fe"]

            elif tool == "api_sms":
                tool_ip = config["api"]["node_ip"]
                tool_port = config["api"]["ports"]["sms"]
                nginx_port = backend_job["ports"]["api_sms"]

            elif tool == "api_warcs":
                tool_ip = config["api"]["node_ip"]
                tool_port = config["api"]["ports"]["warcs"]
                nginx_port = backend_job["ports"]["api_warcs"]

            else:
                logger.warning(f"Unknown tool in nginx configuration: {tool}")
                continue

            # Generate server list without double semicolons
            servers = [f"server {ip}:{tool_port}" for ip in tool_ip]
            nginx_connection_string = "\n        ".join(servers)  # Proper indentation

            # Update the nginx.conf
            run(ssh, f"cd {deployment_path}/nginx/conf && "
                     f"sed -i -e 's|__nginx_{tool}_connection_string__|{nginx_connection_string}|g' "
                     f"-e 's|__nginx_{tool}_port__|{nginx_port}|g' nginx.conf")

        # Deploy systemd unit
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(f"{binary_path}/Services/nginx/nginx.service", service_path)

        run(ssh, f"cd {service_path} && "
                 f"sed -i -e 's|__deployment_path__|{deployment_path}|g' nginx.service")

        # Start nginx service
        run(ssh, "systemctl --user daemon-reload && "
            "systemctl --user enable nginx.service && "
            "systemctl --user start nginx.service")

        logger.info(f"Nginx successfully started on: {backend_job["node_ip"]}")
    except Exception as e:
        logger.error(f"Error in deploying Nginx: {e}")


def deploy_wrapper(func, config, binary_path):
    """Wrapper to spin up each task with its own SSH client"""

    name = func.__name__
    try:
        logger.info(f"=== Starting {name} ===")
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        func(config, binary_path, ssh)
        ssh.close()
        logger.info(f"=== Completed {name} ===")
    except Exception:
        logger.exception(f"{name} failed with exception")

def threaded_deployment(config, binary_path, tasks):
    """Deployment using multi-threading"""

    if tasks == []:
        return
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(deploy_wrapper, fn, config, binary_path): fn.__name__ for fn in tasks}
        for fut in as_completed(futures):
            svc = futures[fut]
            try:
                fut.result()
            except Exception:
                logger.error(f"{svc} raised an unhandled exception")
def main():
    debug_environment()
    base_path = os.path.dirname(os.path.abspath(__file__))
    config = get_config(base_path)
    binary_path = os.path.join(base_path, "..", "Releases")

    # Create SSH client object
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    deploy = config["deploy"]

    try:
        if deploy.get("zookeeper") == "true":
            deploy_zookeeper(config, binary_path, ssh)
        if deploy.get("kafka") == "true":
            deploy_kafka(config, binary_path, ssh)
        if deploy.get("doris_fe") == "true":
            deploy_doris_fe(config, binary_path, ssh)
        if deploy.get("doris_be") == "true":
            deploy_doris_be(config, binary_path, ssh)
        if deploy.get("connect_fe_be") == "true":
            connect_doris_fe_and_be(config, binary_path, ssh)
        if deploy.get("node_exporter") == "true":
            deploy_node_exporter(config, binary_path, ssh)
        if deploy.get("kafka_exporter") == "true":
            deploy_kafka_exporter(config, binary_path, ssh)
        if deploy.get("prometheus") == "true":
            deploy_prometheus(config, binary_path, ssh)
        if deploy.get("grafana") == "true":
            deploy_grafana(config, binary_path, ssh)
        if deploy.get("health_reports") == "true":
            deploy_health_reports(config, binary_path, ssh)
        if deploy.get("recon") == "true":
            deploy_recon(config, binary_path, ssh)
        if deploy.get("jobs") == "true":
            deploy_jobs(config, binary_path, ssh)
        if deploy.get("api") == "true":
            deploy_api(config, binary_path, ssh)
        if deploy.get("nginx") == "true":
            deploy_nginx(config, binary_path, ssh)

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
    finally:
        ssh.close()
# def main():
#     base_path = os.path.dirname(os.path.abspath(__file__))
#     print("Starting Run")
#     config = get_config(base_path)
#     binary_path = os.path.join(base_path, "..", "Releases")

#     tasks1 = []
#     tasks2 = []
#     deploy = config["deploy"]
    
#     print("configs done")
#     if deploy["zookeeper"] == "true":
#         tasks1.append(deploy_zookeeper)
#     if deploy["kafka"] == "true":
#         tasks1.append(deploy_kafka)
#     if deploy["doris_fe"] == "true":
#         tasks1.append(deploy_doris_fe)
#     if deploy["doris_be"] == "true":
#         tasks1.append(deploy_doris_be)
#     if deploy["connect_fe_be"] == "true":
#         print("I am here doris")
#         tasks2.append(connect_doris_fe_and_be)
#     if deploy["node_exporter"] == "true":
#         tasks1.append(deploy_node_exporter)
#     if deploy["kafka_exporter"] == "true":
#         tasks2.append(deploy_kafka_exporter)
#     if deploy["prometheus"] == "true":
#         tasks1.append(deploy_prometheus)
#     if deploy["grafana"] == "true":
#         tasks1.append(deploy_grafana)
#     if deploy["health_reports"] == "true":
#         tasks1.append(deploy_health_reports)
#     if deploy["recon"] == "true":
#         tasks1.append(deploy_recon)
#     if deploy["jobs"] == "true":
#         tasks1.append(deploy_jobs)
#     if deploy["api"] == "true":
#         tasks1.append(deploy_api)
#     if deploy["nginx"] == "true":
#         tasks1.append(deploy_nginx)
    
#     print("checked which packags to install")
#     threaded_deployment(config, binary_path, tasks1)
#     threaded_deployment(config, binary_path, tasks2)

if __name__ == "__main__":
    main()
