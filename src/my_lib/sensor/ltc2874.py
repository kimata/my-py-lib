#!/usr/bin/env python3
# ADI の LTC2874 を使って、IO-LINK 通信を行うライブラリです。

import logging
import pprint
import time

import serial
import spidev

import my_lib.sensor

DEBUG = True

DATA_TYPE_RAW = 0
DATA_TYPE_STRING = 1
DATA_TYPE_UINT16 = 2


def dump_byte_list(label, byte_list):
    logging.debug("%s: %s", label, ", ".join(f"0x{v:02X}" for v in byte_list))


def ltc2874_reg_read(spi, reg):
    recv = spi.xfer2([(0x00 << 5) | (reg << 1), 0x00])

    dump_byte_list("SPI READ", recv)

    return recv[1]


def ltc2874_reg_write(spi, reg, data):
    spi.xfer2([(0x03 << 5) | (reg << 1), data])


def ltc2874_reset(spi):
    logging.info("Reset LTC2874")
    spi.xfer2([0x07 << 5, 0x00])


def msq_checksum(data):
    chk = 0x52
    for d in data:
        chk ^= d

    return (
        ((((chk >> 7) ^ (chk >> 5) ^ (chk >> 3) ^ (chk >> 1)) & 1) << 5)
        | ((((chk >> 6) ^ (chk >> 4) ^ (chk >> 2) ^ (chk >> 0)) & 1) << 4)
        | ((((chk >> 7) ^ (chk >> 6)) & 1) << 3)
        | ((((chk >> 5) ^ (chk >> 4)) & 1) << 2)
        | ((((chk >> 3) ^ (chk >> 2)) & 1) << 1)
        | ((((chk >> 1) ^ (chk >> 0)) & 1) << 0)
    )


def msq_build(rw, ch, addr, mtype, data):
    mc = (rw << 7) | (ch << 5) | (addr)
    cht = mtype << 6

    msq = [mc, cht]

    if data is not None:
        msq.extend(data)

    cht |= msq_checksum(msq)
    msq[1] = cht

    return msq


def com_open():
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1000
    spi.mode = 0

    return spi


def com_close(spi, is_reset=False):
    if is_reset:
        ltc2874_reset(spi)

    spi.close()


def com_status(spi):
    enl1 = ltc2874_reg_read(spi, 0x0E)

    return enl1 == 0x11


def com_start(spi):
    BOOT_WAIT_SEC = 5
    if com_status(spi):
        logging.debug("IO-Link is already Powered-ON")
    else:
        # Power on, CQ OC Timeout = 480us
        logging.info("***** Power-On IO-Link ****")
        ltc2874_reg_write(spi, 0x0E, 0x11)
        logging.info("Wait for device booting (%d sec)", BOOT_WAIT_SEC)
        time.sleep(BOOT_WAIT_SEC)

    # Wakeup
    ltc2874_reg_write(spi, 0x0D, 0x10)

    # Drive enable
    ltc2874_reg_write(spi, 0x0D, 0x01)

    return serial.Serial(
        port="/dev/ttyAMA0",
        baudrate=38400,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.01,
    )


def com_stop(spi, ser=None, is_power_off=False):
    if ser is not None:
        ser.close()

    # Drive disable
    ltc2874_reg_write(spi, 0x0D, 0x00)

    if is_power_off:
        # Power off
        logging.info("***** Power-Off IO-Link ****")
        ltc2874_reg_write(spi, 0x0E, 0x00)


def com_write(spi, ser, byte_list):
    # Drive enable
    ltc2874_reg_write(spi, 0x0D, 0x01)

    dump_byte_list("COM SEND", byte_list)

    ser.write(bytes(byte_list))
    ser.flush()

    # Drive disable
    ltc2874_reg_write(spi, 0x0D, 0x00)


def com_read(spi, ser, length):  # noqa: ARG001
    recv = ser.read(length)
    byte_list = list(recv)

    dump_byte_list("COM RECV", byte_list)

    return byte_list


def dir_param_read(spi, ser, addr):
    logging.debug("***** CALL: dir_param_read(addr: 0x%02X) ****", addr)

    msq = msq_build(
        my_lib.sensor.io_link.MSQ_RW_READ,
        my_lib.sensor.io_link.MSQ_CH_PAGE,
        addr,
        my_lib.sensor.io_link.MSQ_TYPE_0,
        None,
    )
    com_write(spi, ser, msq)

    data = com_read(spi, ser, 4)[2:]

    if len(data) < 2:
        raise OSError("response is too short")  # noqa: EM101, TRY003
    elif data[1] != msq_checksum([data[0]]):  # noqa:RET506
        raise OSError("checksum unmatch")  # noqa: EM101, TRY003

    return data[0]


def dir_param_write(spi, ser, addr, value):
    logging.debug("***** CALL: dir_param_write(addr: 0x%02X, value: 0x%02X) ****", addr, value)

    msq = msq_build(
        my_lib.sensor.io_link.MSQ_RW_WRITE,
        my_lib.sensor.io_link.MSQ_CH_PAGE,
        addr,
        my_lib.sensor.io_link.MSQ_TYPE_0,
        [value],
    )
    com_write(spi, ser, msq)

    data = com_read(spi, ser, 4)[3:]

    if len(data) < 1:
        raise OSError("response is too short")  # noqa: EM101, TRY003
    elif data[0] != msq_checksum([]):  # noqa: RET506
        raise OSError("checksum unmatch")  # noqa: EM101, TRY003


def isdu_req_build(index, length):
    rw = my_lib.sensor.io_link.MSQ_RW_WRITE
    isrv = my_lib.sensor.io_link.ISDU_ISRV_READ_8BIT_IDX

    return [
        msq_build(
            rw,
            my_lib.sensor.io_link.MSQ_CH_ISDU,
            0x10,
            my_lib.sensor.io_link.MSQ_TYPE_0,
            [(isrv << 4) | length],
        ),
        msq_build(rw, my_lib.sensor.io_link.MSQ_CH_ISDU, 0x01, my_lib.sensor.io_link.MSQ_TYPE_0, [index]),
        msq_build(
            rw,
            my_lib.sensor.io_link.MSQ_CH_ISDU,
            0x02,
            my_lib.sensor.io_link.MSQ_TYPE_0,
            [((isrv << 4) | length) ^ index],
        ),
    ]


def isdu_res_read(spi, ser, flow):
    msq = msq_build(
        my_lib.sensor.io_link.MSQ_RW_READ,
        my_lib.sensor.io_link.MSQ_CH_ISDU,
        flow,
        my_lib.sensor.io_link.MSQ_TYPE_0,
        None,
    )
    com_write(spi, ser, msq)

    data = com_read(spi, ser, 4)[2:]

    if len(data) < 2:
        raise OSError("response is too short")  # noqa: EM101, TRY003
    if data[1] != msq_checksum([data[0]]):
        raise OSError("checksum unmatch")  # noqa: EM101, TRY003

    return data[0]


def isdu_read(spi, ser, index, data_type):  # noqa: PLR0912, C901
    logging.debug("***** CALL: isdu_read(index: 0x%02X) ****", (index))
    length = 3

    isdu_req = isdu_req_build(index, length)

    for msq in isdu_req:
        com_write(spi, ser, msq)
        data = com_read(spi, ser, 4)

    chk = 0x00
    flow = 1
    data_list = []
    while True:
        header = isdu_res_read(spi, ser, 0x10)
        chk = header

        if (header >> 4) == 0x0D:
            if (header & 0x0F) == 0x01:
                remain = isdu_res_read(spi, ser, flow) - 2
                flow += 1
                chk ^= length
            else:
                remain = (header & 0x0F) - 1
            break
        elif header == 0x01:  # noqa:RET508
            logging.warning("WAIT response")
            continue
        elif (header >> 4) == 0x0C:
            raise OSError("ERROR reponse")  # noqa: EM101, TRY003
        else:
            raise OSError(f"INVALID response: {pprint.pformat(header)}")  # noqa: EM102, TRY003

    for _ in range(remain - 1):
        data = isdu_res_read(spi, ser, flow & 0xF)
        data_list.append(data)
        flow += 1
        chk ^= data

    chk ^= isdu_res_read(spi, ser, flow)

    if chk != 0x00:
        raise OSError("ISDU checksum unmatch")  # noqa: EM101, TRY003

    if data_type == DATA_TYPE_STRING:
        return bytes(data_list).decode("utf-8")
    elif data_type == DATA_TYPE_UINT16:
        return int.from_bytes(data_list, byteorder="big")
    else:
        return data_list
