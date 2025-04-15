import time
from netmiko import ConnectHandler



ROUTERS = {
    'router1': {
        'device_type': 'linux',
        'host': '192.168.1.1',
        'username': 'admin',
        'password': 'password',
    },
    'router2': {
        'device_type': 'linux',
        'host': '192.168.1.2',
        'username': 'admin',
        'password': 'password',
    }
}

BGP_NEIGHBOR_IP = "1.1.1.1"
TARGET_PREFIXES = [
"192.168.10.0/24",
    # "192.168.20.0/24",             
]
BGP_AS = "65000"
CHECK_INTERVAL_PHASE1 = 5
CHECK_INTERVAL_PHASE2 = 300



def enter_vtysh(conn):
    """FRR Router"""
    conn.write_channel("vtysh\n")
    time.sleep(1)
    conn.read_channel()  
    return conn

def check_bgp_advertisement(router, neighbor_ip, prefix):
    try:
        with ConnectHandler(**router) as conn:
            enter_vtysh(conn)
            output = conn.send_command(
                f"show ip bgp neighbors {neighbor_ip} advertised-routes",
                expect_string=r"#"
            )
            return prefix in output
    except Exception as e:
        print(f"[{time.ctime()}] ❌ Error checking BGP on {router['host']}: {str(e)}")
        return None

def modify_bgp_advertisement(router, action, prefix, as_number):
    if action == 'inject':
        cmd = f"network {prefix}"
    elif action == 'remove':
        cmd = f"no network {prefix}"
    else:
        print(f"[{time.ctime()}] ❗ Invalid BGP action: {action}")
        return False

    try:
        with ConnectHandler(**router) as conn:
            enter_vtysh(conn)

            conn.send_command("configure terminal", expect_string=r"#")
            conn.send_command(f"router bgp {as_number}", expect_string=r"#")
            conn.send_command("address-family ipv4 unicast", expect_string=r"#")
            conn.send_command(cmd, expect_string=r"#")
            conn.send_command("end", expect_string=r"#")

            try:
                conn.send_command("clear bgp ipv4 * soft", expect_string=r"#")
            except:
                pass

            return True
    except Exception as e:
        print(f"[{time.ctime()}] ❌ Error modifying BGP on {router['host']}: {str(e)}")
        return False



def main():
    phase = 1
    last_action = {prefix: None for prefix in TARGET_PREFIXES}

    while True:
        try:
            if phase == 1:
                for prefix in TARGET_PREFIXES:
                    adv_present = check_bgp_advertisement(ROUTERS['router1'], BGP_NEIGHBOR_IP, prefix)

                    if adv_present is None:
                        time.sleep(10)
                        continue

                    if not adv_present and last_action[prefix] != 'injected':
                        success = modify_bgp_advertisement(ROUTERS['router2'], 'inject', prefix, BGP_AS)
                        if success:
                            print(f"[{time.ctime()}] ✅ Injected {prefix} on Router 2")
                            last_action[prefix] = 'injected'
                            phase = 2
                    else:
                        print(f"[{time.ctime()}] ✅ Advertisement for {prefix} is present")

                time.sleep(CHECK_INTERVAL_PHASE1)

            elif phase == 2:
                print(f"[{time.ctime()}] 🔁 Phase 2 - Checking every {CHECK_INTERVAL_PHASE2} seconds...")
                time.sleep(CHECK_INTERVAL_PHASE2)

                for prefix in TARGET_PREFIXES:
                    adv_present = check_bgp_advertisement(ROUTERS['router1'], BGP_NEIGHBOR_IP, prefix)

                    if adv_present is None:
                        continue

                    if adv_present and last_action[prefix] == 'injected':
                        success = modify_bgp_advertisement(ROUTERS['router2'], 'remove', prefix, BGP_AS)
                        if success:
                            print(f"[{time.ctime()}] 🔄 Removed {prefix} from Router 2")
                            last_action[prefix] = 'removed'
                            phase = 1
                    else:
                        print(f"[{time.ctime()}] ⚠️ Advertisement for {prefix} still missing")

        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user.")
            break
        except Exception as e:
            print(f"[{time.ctime()}] ⚠️ Unexpected error: {str(e)}")
            time.sleep(30)



if __name__ == "__main__":
    print(f"🚀 Starting BGP Advertisement Monitor for: {', '.join(TARGET_PREFIXES)}")
    main()
