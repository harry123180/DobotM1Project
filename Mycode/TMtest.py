from pymodbus.client import ModbusTcpClient
import time

def write_incremental_values(ip, port, slave_id, address):
    client = ModbusTcpClient(ip, port=port)
    client.connect()
    
    value = 1
    while True:
        rr = client.write_register(address, value, slave=slave_id)
        if rr.isError():
            print(f"寫入錯誤，value={value}")
        else:
            print(f"成功寫入 {value} 到地址 {address} (Slave ID: {slave_id})")
        value += 1
        time.sleep(1)
    
    client.close()

if __name__ == "__main__":
    IP = "192.168.0.121"
    PORT = 502
    SLAVE_ID = 1
    ADDRESS = 9000
    
    write_incremental_values(IP, PORT, SLAVE_ID, ADDRESS)
