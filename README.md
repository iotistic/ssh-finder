# SSH Finder Script

## Overview

SSH Finder is a utility designed to help users quickly identify accessible SSH hosts within a given network range and attempt login using specified credentials. It is useful for system administrators, security researchers, and network engineers who need to audit SSH access or locate their devices within a network. The script automates host discovery, credential testing, and login reporting with configurable options.

## Features

- Pure Python implementation using paramiko for SSH connections
- Supports both inline and file-based input for hosts, users, and passwords
- Interactive mode for entering username and password if not provided via arguments
- Parallel SSH login attempts for efficiency
- Optional ping and port availability checks
- Customizable SSH connection timeout
- Logging and verbosity controls
- Secret mode for password input
- Detailed success report with SSH connection commands

## Setup

Ensure you have Python 3.6+ installed, then install required dependencies:

```sh
pip install paramiko tqdm

git clone https://github.com/iotistic/ssh-finder.git
cd ssh-finder
chmod +x ssh_finder.py
sudo ln -s "$PWD/ssh_finder.py" /usr/local/bin/ssh-finder
```

## Usage

Run the script using Python:

```sh
ssh-finder [OPTIONS]
```

### Basic Example

```sh
ssh-finder -H 192.168.1.0/24
```

Or specify credentials:

```sh
ssh-finder -H 192.168.1.0/24 -u <username> -p <password>
```

If `-u` or `-p` is not specified, the script will prompt for interactive input.

#### Example Output

```
$ ssh-finder -H 192.168.1.0/24 -u mnvr -p 123

2025-03-18 12:02:59,386 - INFO - Reading usernames...
2025-03-18 12:02:59,387 - INFO - Reading passwords...
2025-03-18 12:02:59,387 - INFO - Parsing hosts and filtering reachable hosts with open SSH port...
2025-03-18 12:02:59,387 - INFO - Checking ping for reachable hosts with timeout 1 sec...
2025-03-18 12:03:01,835 - INFO - Found 62 reachable hosts.
2025-03-18 12:03:01,835 - INFO - Checking SSH port 22 for reachable hosts...
2025-03-18 12:03:12,493 - INFO - Found 16
Trying combinations:  19%|█████████████████████▌                             | 3/16 [00:00<00:01,  7.60it/s]
2025-03-18 12:03:13,097 - INFO - ✅ SUCCESSFUL LOGIN! mnvr@192.168.1.223 with password: 123
Trying combinations: 100%|██████████████████████████████████████████████████| 16/16 [00:04<00:00,  3.77it/s]


===== LOGIN ATTEMPT REPORT =====
Generated on: 2025-03-18 12:03:16
Total combinations attempted: 16
Successful logins: 1
Failed attempts: 15
Success rate: 6.25%
---------------------------------
Successful Combinations:
  ✅ Host: 192.168.1.223 | User: mnvr | Password: 123
      → SSH Command: ssh mnvr@192.168.1.223
=================================
```

#### Interactive and Secret modes example

```
$ ssh-finder -H 192.168.1.0/24 -s
2025-03-23 13:55:57,496 - INFO - Reading usernames...
Enter your SSH username: mnvr
2025-03-23 13:56:00,092 - INFO - Reading passwords...
Enter your SSH password:
2025-03-23 13:56:01,657 - INFO - Parsing hosts and filtering reachable hosts with open SSH port...
2025-03-23 13:56:01,658 - INFO - Checking ping for reachable hosts with timeout 1 sec...
2025-03-23 13:56:04,706 - INFO - Found 46 reachable hosts.
2025-03-23 13:56:04,706 - INFO - Checking SSH port 22 for reachable hosts...
2025-03-23 13:56:13,847 - INFO - Found 15
Trying combinations:  27%|██████████████████████████████████████████████▍    | 4/15 [00:00<00:02,  5.39it/s]
2025-03-23 13:56:15,291 - INFO - ✅ SUCCESSFUL LOGIN! mnvr@192.168.1.148 with password: ********
Trying combinations:  33%|███████████████████████████████████████████████████ | 5/15 [00:01<00:03,  2.90it/s]
2025-03-23 13:56:15,457 - INFO - ✅ SUCCESSFUL LOGIN! mnvr@192.168.1.140 with password: ********
Trying combinations: 100%|███████████████████████████████████████████████████| 15/15 [00:04<00:00,  3.36it/s]


===== LOGIN ATTEMPT REPORT =====
Generated on: 2025-03-23 13:56:18
Total combinations attempted: 15
Successful logins: 2
Failed attempts: 13
Success rate: 13.33%
---------------------------------
Successful Combinations:
  ✅ Host: 192.168.1.140 | User: mnvr | Password: ********
      → SSH Command: ssh mnvr@192.168.1.140
  ✅ Host: 192.168.1.148 | User: mnvr | Password: ********
      → SSH Command: ssh mnvr@192.168.1.148
=================================
```

## Options

### Host Options

- `-H, --hosts` : Comma-separated list of hosts/subnets
- `--hosts-file` : File containing list of hosts/subnets

### Authentication Options

- `-p, --passwords` : Comma-separated list of passwords
- `--passwords-file` : File containing passwords
- `-u, --users` : Comma-separated list of usernames
- `--users-file` : File containing multiple usernames
- **Interactive Mode**: If no username or password is provided, the script will prompt for input
- `-s, --secret` : Enable secret mode for password input (masks password in logs)

### Logging & Output Options

- `-l, --log-file` : Specify log file location (default: `ssh_attempts.log`)
- `-q, --quiet` : Suppress most output (only warnings and errors)
- `-v, --verbose` : Enable detailed debug logs

### Connection Options

- `--ssh-timeout` : SSH connection timeout in seconds (default: `10`)
- `-c, --connect-on-first-success` : Stop script and show SSH command on first success
- `--port` : SSH port to check (default: `22`)

### Ping & Port Checks

- `--skip-ping` : Skip ping check
- `--ping-timeout` : Set ping timeout (default: `1` second)
- `--ping-pool-size` : Maximum concurrent ping processes
- `--skip-port-check` : Skip checking if SSH port is open
- `--port-timeout` : Timeout for port check (default: `1` second)

### Parallelism

- `--max-threads` : Maximum parallel SSH attempts (default: `100`)

## Notes

- Requires Python 3.6+ and paramiko library
- Automatically adds new hosts to known_hosts (no host key verification)
- Passwords are masked in logs when using secret mode
- Use responsibly and only on networks you have permission to scan
- The script doesn't store any credentials after execution
