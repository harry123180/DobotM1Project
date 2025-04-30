from pymodbus.client import ModbusTcpClient

class Vibration_plate:
    def __init__(self, ip, port, slave_id):
        self.client = ModbusTcpClient(host=ip, port=port)
        self.slave_id = slave_id
        if self.client.connect():
            print(f"✅ Connected to {ip}:{port} (slave ID {slave_id})")
        else:
            raise ConnectionError("❌ Unable to connect to Modbus server")

    def write_register(self, address, value):
        response = self.client.write_register(address=address, value=value, slave=self.slave_id)
        if response.isError():
            print(f"⚠️ Failed to write to register {address}: {response}")
        else:
            print(f"✅ Register {address} set to {value}")

    def backlight(self, state):
        self.write_register(58, int(bool(state)))  # 58: 背光開關

    def trigger_action(self, action_id):
        self.write_register(4, action_id)  # 4: 單一動作觸發

    def up(self, strength, frequency):
        self.write_register(20, strength)  # 強度
        self.write_register(60, frequency) # 頻率
        self.trigger_action(1)

    def down(self, strength, frequency):
        self.write_register(21, strength)
        self.write_register(61, frequency)
        self.trigger_action(2)

    def left(self, strength, frequency):
        self.write_register(22, strength)
        self.write_register(62, frequency)
        self.trigger_action(3)

    def right(self, strength, frequency):
        self.write_register(23, strength)
        self.write_register(63, frequency)
        self.trigger_action(4)

    def upleft(self, strength, frequency):
        self.write_register(24, strength)
        self.write_register(64, frequency)
        self.trigger_action(5)

    def downleft(self, strength, frequency):
        self.write_register(25, strength)
        self.write_register(65, frequency)
        self.trigger_action(6)

    def upright(self, strength, frequency):
        self.write_register(26, strength)
        self.write_register(66, frequency)
        self.trigger_action(7)

    def downright(self, strength, frequency):
        self.write_register(27, strength)
        self.write_register(67, frequency)
        self.trigger_action(8)

    def horizontal(self, strength, frequency):
        self.write_register(28, strength)
        self.write_register(68, frequency)
        self.trigger_action(9)

    def vertical(self, strength, frequency):
        self.write_register(29, strength)
        self.write_register(69, frequency)
        self.trigger_action(10)

    def spread(self, strength, frequency):
        self.write_register(30, strength)
        self.write_register(70, frequency)
        self.trigger_action(11)
    def stop(self):
        """停止所有單一動作"""
        self.write_register(4, 0)
        print("🛑 動作已停止")

    def close(self):
        self.client.close()
        print("🔌 Modbus TCP connection closed.")
