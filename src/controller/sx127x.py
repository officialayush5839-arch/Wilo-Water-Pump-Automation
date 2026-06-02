import time

import RPi.GPIO as GPIO
import spidev

# Register Constants (SX127x)
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_LNA = 0x0C
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_TX_BASE_ADDR = 0x0E
REG_FIFO_RX_BASE_ADDR = 0x0F
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_SNR_VALUE = 0x19
REG_PKT_RSSI_VALUE = 0x1A
REG_MODEM_CONFIG_1 = 0x1D
REG_MODEM_CONFIG_2 = 0x1E
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_MODEM_CONFIG_3 = 0x26
REG_RSSI_WIDEBAND = 0x2C
REG_DETECTION_OPTIMIZE = 0x31
REG_INVERT_IQ = 0x33
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42

# Modes
MODE_LONG_RANGE_MODE = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_RX_CONTINUOUS = 0x05

# PA Config
PA_BOOST = 0x80

# IRQ Flags
IRQ_PAYLOAD_CRC_ERROR_MASK = 0x20
IRQ_RX_DONE_MASK = 0x40


class SX127x:
    def __init__(self, spi_bus=0, spi_cs=0, reset_pin=25, dio0_pin=24, frequency=433E6):
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_cs)
        # Stay conservative without dropping so low that basic register access
        # becomes unreliable on the Pi.
        self.spi.max_speed_hz = 500000

        self.reset_pin = reset_pin
        self.dio0_pin = dio0_pin
        self.frequency = frequency

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.reset_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.dio0_pin, GPIO.IN)

        self.reset()
        self.init()

    def reset(self):
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.02)
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.02)

    def write_register(self, addr, value):
        self.spi.xfer2([addr | 0x80, value])

    def read_register(self, addr):
        resp = self.spi.xfer2([addr & 0x7F, 0x00])
        return resp[1]

    def init(self):
        version = 0x00
        for _ in range(10):
            version = self.read_register(REG_VERSION)
            if version == 0x12:
                break
            time.sleep(0.05)

        if version != 0x12:
            print(f"Warning: Unknown LoRa chip version: 0x{version:02X}")
        else:
            print(f"SX127x Version: 0x{version:02X}")

        self.sleep()
        self.write_register(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_SLEEP)
        self.standby()

        self.set_frequency(self.frequency)
        self.write_register(REG_FIFO_TX_BASE_ADDR, 0x00)
        self.write_register(REG_FIFO_RX_BASE_ADDR, 0x00)
        self.write_register(REG_LNA, self.read_register(REG_LNA) | 0x03)
        self.write_register(REG_MODEM_CONFIG_3, 0x04)
        self.write_register(REG_MODEM_CONFIG_1, 0x72)
        self.write_register(REG_MODEM_CONFIG_2, 0x70)
        self.write_register(REG_PREAMBLE_MSB, 0x00)
        self.write_register(REG_PREAMBLE_LSB, 0x08)
        self.write_register(REG_SYNC_WORD, 0xF3)
        self.write_register(REG_PA_CONFIG, PA_BOOST | 0x0F)

    def set_frequency(self, freq):
        self.frequency = freq
        frf = int((freq * 524288) / 32000000)
        self.write_register(REG_FRF_MSB, (frf >> 16) & 0xFF)
        self.write_register(REG_FRF_MID, (frf >> 8) & 0xFF)
        self.write_register(REG_FRF_LSB, frf & 0xFF)

    def sleep(self):
        self.write_register(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_SLEEP)

    def standby(self):
        self.write_register(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_STDBY)

    def receive(self):
        self.write_register(REG_FIFO_ADDR_PTR, 0x00)
        self.write_register(REG_DIO_MAPPING_1, 0x00)
        self.write_register(REG_IRQ_FLAGS, 0xFF)
        self.write_register(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_RX_CONTINUOUS)

    def available(self):
        irq_flags = self.read_register(REG_IRQ_FLAGS)
        if irq_flags & IRQ_PAYLOAD_CRC_ERROR_MASK:
            self.write_register(REG_IRQ_FLAGS, irq_flags)
            return False
        if irq_flags & IRQ_RX_DONE_MASK:
            self.write_register(REG_IRQ_FLAGS, irq_flags)
            return True
        return False

    def get_packet_rssi(self):
        rssi = self.read_register(REG_PKT_RSSI_VALUE)
        return rssi - 164

    def get_packet_snr(self):
        raw_snr = self.read_register(REG_PKT_SNR_VALUE)
        if raw_snr > 127:
            raw_snr -= 256
        return raw_snr * 0.25

    def read_payload(self):
        length = self.read_register(REG_RX_NB_BYTES)
        if length <= 0 or length > 255:
            return []

        current_addr = self.read_register(REG_FIFO_RX_CURRENT_ADDR)
        self.write_register(REG_FIFO_ADDR_PTR, current_addr)

        payload = []
        for _ in range(length):
            payload.append(self.read_register(REG_FIFO))
        return payload

    def close(self):
        self.spi.close()
        # Do not reset unrelated GPIOs such as the pump relay pin.
        # A global cleanup() here can leave the relay input floating.
        GPIO.cleanup([self.reset_pin, self.dio0_pin])
