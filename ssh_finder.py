#!/usr/bin/env python3
import multiprocessing
from datetime import datetime
import shutil
from tqdm import tqdm
import subprocess
import logging
import ipaddress
import argparse
import socket
import shlex
import concurrent.futures
import sys

MAX_PING_PROCESSES = 100
MAX_SSH_PROCESSES = 100


def parse_arguments():
    """
    Parse command-line arguments and return them.
    """
    excutable_name = sys.argv[0].split("/")[-1]

    parser = argparse.ArgumentParser(
        description="SSH Finder script with parallel attempts, host filtering via fping, extra SSH options, "
                    "and configurable ping/port checks.",
        epilog=f"""
Examples:
  {excutable_name} -H 192.168.1.1,192.168.1.2 -p pass123,rootpass -u admin
  {excutable_name} -H 192.168.1.100 -p pass123 -u admin --ssh-options "-p 2222 -o ConnectTimeout=5"
  {excutable_name} -H 192.168.1.0/30 -p pass123 --users-file users.txt --users admin,root
  {excutable_name} -H 192.168.1.1 -p pass123 -u admin --login-on-first-success
  {excutable_name} -H 192.168.1.1,192.168.1.2 -p pass123,rootpass --skip-ping --skip-port-check
""", formatter_class=argparse.RawTextHelpFormatter)

    # Host options
    host_group = parser.add_mutually_exclusive_group(required=True)
    host_group.description = "Specify the hosts to attempt login to."

    host_group.add_argument("-H", "--hosts",
                            help="Comma-separated list of hosts or subnets (e.g., 192.168.1.1,192.168.1.2/24)")
    host_group.add_argument("--hosts-file",
                            help="File containing list of hosts/subnets (default: hosts.txt)")

    # Password options
    password_group = parser.add_mutually_exclusive_group()
    password_group.description = "Specify the password(s) to use for SSH login. If not provided, the script will prompt for a password."

    password_group.add_argument("-p", "--password", "--passwords",
                                help="Comma-separated list of passwords (e.g., pass123,rootpass)")
    password_group.add_argument("--passwords-file",
                                help="File containing passwords (default: passwords.txt)")

    # User options
    user_group = parser.add_mutually_exclusive_group()
    user_group.description = "Specify the username(s) to use for SSH login. If not provided, the script will prompt for a username."

    user_group.add_argument("-u", "--user", "--users",
                            help="Comma-separated list of usernames (e.g., admin,root)")
    user_group.add_argument("--users-file",
                            help="File containing multiple usernames (one per line)")

    # Logging and SSH options
    parser.add_argument("-l", "--log-file", default="ssh_attempts.log",
                        help="Log file location (default: ssh_attempts.log)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress most output (only warnings and errors)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show detailed logs")
    parser.add_argument("--ssh-options",
                        help="Extra SSH options (e.g., '-p 2222 -o ConnectTimeout=5')", default="")

    # Control exit behavior: default is to wait for all attempts;
    # if --login-on-first-success is provided, exit immediately on first success.
    parser.add_argument("-c", "--connect-on-first-success", action="store_true",
                        help="Stop script and open interactive SSH session on first successful login.")

    # Ping check options
    parser.add_argument("--skip-ping", action="store_true",
                        help="Skip the ping check for hosts.")
    parser.add_argument("--ping-timeout", type=int, default=1,
                        help="Ping timeout in seconds (default: 1).")
    parser.add_argument("--ping-pool-size", type=int, default=MAX_PING_PROCESSES,
                        help=f"Maximum number of ping processes (default: {MAX_PING_PROCESSES}).")

    # Port check options
    parser.add_argument("--skip-port-check", action="store_true",
                        help="Skip checking if the SSH port is open.")
    parser.add_argument("--port", type=int, default=22,
                        help="Port to check for SSH (default: 22).")
    parser.add_argument("--port-timeout", type=int, default=1,
                        help="Timeout in seconds for port check (default: 1).")

    # Parallelism options
    parser.add_argument("--max-threads", type=int, default=MAX_SSH_PROCESSES,
                        help=f"Maximum number of threads for parallel ssh attempts (default: {MAX_SSH_PROCESSES}).")

    # Enable secret mode for password input.
    parser.add_argument("-s", "--secret", action="store_true",
                        help="Enable secret mode for password input.")

    return parser.parse_args()


def setup_logging(args):
    """
    Configure logging based on command-line arguments.
    """
    log_level = logging.INFO
    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(args.log_file)
        ]
    )


def ping_host(host, ping_timeout):
    """
    Use the ping command to check if a single host is reachable.
    Returns the host if it is reachable, otherwise None.
    """
    cmd = ["ping", "-c", "1", "-W", str(ping_timeout), host]
    logging.debug(
        f"Checking ping for {host} with timeout {ping_timeout} sec...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    return host if result.returncode == 0 else None


def check_reachable_hosts(hosts, args):
    """
    Use ping to check which hosts are reachable.
    Returns a set of reachable hosts.
    """
    hosts = set(hosts)

    if args.skip_ping:
        return hosts

    ping_timeout = args.ping_timeout

    # If the number of hosts is greater than 5, use multiprocessing to speed up the pings
    if len(hosts) > 5:
        # Use multiprocessing Pool to ping hosts in parallel
        logging.debug(
            f"Using multiprocessing to ping {len(hosts)} hosts in parallel...")
        pool_size = min(args.ping_pool_size, len(hosts))
        with multiprocessing.Pool(pool_size) as pool:
            reachable_hosts = pool.starmap(
                ping_host, [(host, ping_timeout) for host in hosts])
        reachable = {host for host in reachable_hosts if host is not None}
    else:
        # For fewer hosts, we can ping sequentially
        reachable = {host for host in hosts if ping_host(
            host, ping_timeout) is not None}

    logging.debug(f"Reachable hosts: {reachable}")
    return reachable


def is_ssh_port_open(host, args):
    """
    Check if the specified port is open on the host unless skipped.
    """
    if args.skip_port_check:
        logging.debug(f"Skipping port check for host: {host}")
        return True

    try:
        logging.debug(
            f"Checking if port {args.port} is open on {host} (timeout={args.port_timeout})")
        with socket.create_connection((host, args.port), timeout=args.port_timeout):
            logging.debug(f"Port {args.port} is open on {host}.")
            return True
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logging.debug(f"Port {args.port} is closed on {host}. Error: {e}")
        return False


def parse_hosts(args):
    """
    Parse hosts from inline input or file, expand subnets, and filter hosts that are reachable
    and have the SSH port open.
    """
    logging.info(
        "Parsing hosts and filtering reachable hosts with open SSH port...")
    hosts = []
    lines = []

    if args.hosts:
        lines.extend(args.hosts.split(','))
    elif args.hosts_file:
        try:
            with open(args.hosts_file, "r") as f:
                lines.extend([line.strip()
                             for line in f.readlines() if line.strip()])
        except FileNotFoundError:
            logging.error(f"Hosts file {args.hosts_file} not found!")
            sys.exit(1)
    else:
        logging.error("No hosts provided! Use -H or --hosts.")
        sys.exit(1)

    # Expand subnets.
    for line in lines:
        try:
            network = ipaddress.ip_network(line, strict=False)
            hosts.extend(str(ip) for ip in network.hosts())
        except ValueError:
            hosts.append(line)

    logging.debug(f"Expanded hosts list: {hosts}")

    # Filter by ping using fping (if not skipped).
    if not args.skip_ping:
        logging.info(
            f"Checking ping for reachable hosts with timeout {args.ping_timeout} sec...")
        reachable = check_reachable_hosts(hosts, args)
        logging.info(f"Found {len(reachable)} reachable hosts.")
        logging.debug(f"Reachable hosts: {reachable}")
    else:
        logging.debug("Skipping ping check for all hosts.")
        reachable = set(hosts)

    # Next, filter the hosts for open SSH port.
    logging.info(f"Checking SSH port {args.port} for reachable hosts...")
    filtered_hosts = [
        host for host in reachable if is_ssh_port_open(host, args)]
    if not filtered_hosts:
        logging.error("No reachable hosts with open SSH port found.")
        sys.exit(1)

    logging.info(f"Found {len(filtered_hosts)}")
    logging.debug(f"Filtered hosts: {filtered_hosts}")
    return filtered_hosts


def obfuscate_if_secret(password, args):
    """
    Obfuscate the password for logging purposes.
    """
    if args.secret:
        return "*" * 8
    return password


def read_passwords(args):
    """
    Read passwords from inline input or file.
    """
    logging.info("Reading passwords...")

    passwords = []
    if args.passwords:
        passwords.extend(args.passwords.split(','))
    elif args.passwords_file:
        try:
            with open(args.passwords_file, "r") as f:
                passwords.extend([line.strip()
                                 for line in f.readlines() if line.strip()])
        except FileNotFoundError:
            logging.error(f"Password file {args.passwords_file} not found!")
            sys.exit(1)
    else:
        if args.secret:
            import getpass
            passwords.append(getpass.getpass("Enter your SSH password: "))
        else:
            passwords.append(input("Enter your SSH password: "))

    if not passwords:
        logging.error("No passwords provided! Use -p or --passwords.")
        sys.exit(1)

    return passwords


def read_users(args):
    """
    Read usernames from inline input, file, or prompt the user.
    """
    logging.info("Reading usernames...")

    users = []
    if args.users:
        users.extend(args.users.split(','))
    elif args.users_file:
        try:
            with open(args.users_file, "r") as f:
                users.extend([line.strip()
                             for line in f.readlines() if line.strip()])
        except FileNotFoundError:
            logging.error(f"User file {args.users_file} not found!")
            sys.exit(1)
    if not users:
        users.append(input("Enter your SSH username: "))

    if not users:
        logging.error("No usernames provided! Use -u or --users.")
        sys.exit(1)

    return users


def attempt_ssh_login(host, user, password, ssh_options, args):
    """
    Attempt an SSH login to the given host using the provided user, password,
    and extra SSH options. If successful, open an interactive SSH session.
    """
    logging.debug(
        f"Attempting SSH login for {user}@{host} with password: {obfuscate_if_secret(password, args)}")
    ssh_command = ["sshpass", "-p", password, "ssh", "-o",
                   "StrictHostKeyChecking=no"] + ssh_options + [f"{user}@{host}", "exit"]

    if args.port != 22:
        ssh_command.extend(["-p", str(args.port)])

    try:
        result = subprocess.run(
            ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            success_message = f"✅ SUCCESSFUL LOGIN! {user}@{host} with password: {obfuscate_if_secret(password, args)}"
            logging.info(success_message)
            if args.connect_on_first_success:
                print(
                    f"Opening interactive SSH session to {host} as {user}...")
                interactive_ssh_command = ["sshpass", "-p", password, "ssh", "-o",
                                           "StrictHostKeyChecking=no"] + ssh_options + [f"{user}@{host}"]
                subprocess.run(interactive_ssh_command)
            return True
        else:
            logging.debug(
                f"Failed login for {user}@{host} with password: {obfuscate_if_secret(password, args)}")
            return False
    except FileNotFoundError:
        if not shutil.which("sshpass"):
            logging.error(
                "sshpass is not installed. Please install sshpass to proceed.")
            sys.exit(1)
        logging.error(f"Error connecting to {host} as {user}: {e}")
    except Exception as e:
        logging.error(f"Error connecting to {host} as {user}: {e}")
        return False


def generate_report(successful_combos, total_combinations, args):
    """
    Generate and return a detailed summary report string with enhanced formatting.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    successful_count = len(successful_combos)
    failed_attempts = total_combinations - successful_count
    success_rate = (successful_count / total_combinations) * \
        100 if total_combinations > 0 else 0

    report_lines = [
        "===== LOGIN ATTEMPT REPORT =====",
        f"Generated on: {timestamp}",
        f"Total combinations attempted: {total_combinations}",
        f"Successful logins: {successful_count}",
        f"Failed attempts: {failed_attempts}",
        f"Success rate: {success_rate:.2f}%",
        "---------------------------------"
    ]

    if successful_combos:
        report_lines.append("Successful Combinations:")
        sorted_combos = sorted(
            successful_combos, key=lambda x: x[0])  # Sort by host
        for host, user, password in sorted_combos:
            report_lines.append(
                f"  ✅ Host: {host} | User: {user} | Password: {obfuscate_if_secret(password, args)}"
                f"      → SSH Command: ssh {user}@{host}")

    else:
        report_lines.append("No successful logins recorded.")

    report_lines.append("=================================")

    return "\n".join(report_lines)


def main():
    args = parse_arguments()
    setup_logging(args)

    users = read_users(args)
    passwords = read_passwords(args)
    hosts = parse_hosts(args)
    ssh_options = shlex.split(args.ssh_options)

    # Create all combinations of host, user, and password.
    combinations = [(host, user, password)
                    for user in users for password in passwords for host in hosts]
    total_combinations = len(combinations)
    logging.debug(
        f"Attempting {total_combinations} connection combinations in parallel...")

    successful_combos = []

    use_progress_bar = not (args.verbose or args.quiet)

    pool_size = min(args.max_threads, total_combinations)

    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
        future_to_combo = {
            executor.submit(attempt_ssh_login, host, user, password, ssh_options, args): (host, user, password)
            for host, user, password in combinations
        }

        progress_bar = tqdm(total=total_combinations,
                            desc="Trying combinations", disable=not use_progress_bar)

        for future in concurrent.futures.as_completed(future_to_combo):
            combo = future_to_combo[future]
            progress_bar.update(1)
            try:
                if future.result():
                    logging.debug(
                        f"Login successful for {combo[1]}@{combo[0]}")
                    successful_combos.append(combo)
                    if args.connect_on_first_success:
                        progress_bar.close()
                        logging.info(report)
                        sys.exit(0)
            except Exception as exc:
                logging.error(
                    f"Exception during SSH attempt for {combo[1]}@{combo[0]}: {exc}")

        progress_bar.close()

    report = generate_report(successful_combos, total_combinations, args)
    print("\n")
    print(report)

    sys.exit(0 if successful_combos else 1)


if __name__ == "__main__":
    main()
