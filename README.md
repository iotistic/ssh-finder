# ssh-finder

Use to find which host is yours and ssh into it

`python3 ssh_finder.py -H 192.168.1.0/24`
or
`python3 ssh_finder.py -H 192.168.1.0/24 -u <username> -p <password>`

example:

```
# python3 ssh_finder.py -H 192.168.1.0/24 -u mnvr -p 123 

2025-03-18 12:02:59,386 - INFO - Reading usernames...
2025-03-18 12:02:59,387 - INFO - Reading passwords...
2025-03-18 12:02:59,387 - INFO - Parsing hosts and filtering reachable hosts with open SSH port...
2025-03-18 12:02:59,387 - INFO - Checking ping for reachable hosts with timeout 1 sec...
2025-03-18 12:03:01,835 - INFO - Found 62 reachable hosts.
2025-03-18 12:03:01,835 - INFO - Checking SSH port 22 for reachable hosts...
2025-03-18 12:03:12,493 - INFO - Found 16
Trying combinations:  19%|█████████████████████▌                                                                                             | 3/16 [00:00<00:01,  7.60it/s]
2025-03-18 12:03:13,097 - INFO - ✅ SUCCESSFUL LOGIN! mnvr@192.168.1.223 with password: 123
Trying combinations: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 16/16 [00:04<00:00,  3.77it/s]


===== LOGIN ATTEMPT REPORT =====
Generated on: 2025-03-18 12:03:16
Total combinations attempted: 16
Successful logins: 1
Failed attempts: 15
Success rate: 6.25%
---------------------------------
Successful Combinations:
  ✅ Host: 192.168.1.223 | User: mnvr | Password: 123      → SSH Command: ssh mnvr@192.168.1.223
=================================
```
