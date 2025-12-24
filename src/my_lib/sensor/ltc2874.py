#!/usr/bin/env python3
# ADI の LTC2874 を使って、IO-LINK 通信を行うライブラリです。

from __future__ import annotations

import logging
import pprint
import time
from typing import Any

import serial
import spidev

import my_lib.sensor
import my_lib.sensor.io_link
from my_lib.sensor.exceptions import SensorCommunicationError, SensorCRCError

DEBUG: bool = True

DATA_TYPE_RAW: int = 0
DATA_TYPE_STRING: int = 1
DATA_TYPE_UINT16: int = 2


def dump_byte_list(label: str, byte_list: list[int]) -> None:
    logging.debug("%s: %s", label, ", ".join(f"0x{v:02X}" for v in byte_list))


def ltc2874_reg_read(spi: spidev.SpiDev, reg: int) -> int:
    recv = spi.xfer2([(0x00 << 5) | (reg << 1), 0x00])

    dump_byte_list("SPI READ", recv)

    return recv[1]


def ltc2874_reg_write(spi: spidev.SpiDev, reg: int, data: int) -> None:
    spi.xfer2([(0x03 << 5) | (reg << 1), data])


def ltc2874_reset(spi: spidev.SpiDev) -> None:
    logging.info("Reset LTC2874")
    spi.xfer2([0x07 << 5, 0x00])


def msq_checksum(data: list[int]) -> int:
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


def msq_build(rw: int, ch: int, addr: int, mtype: int, data: list[int] | None) -> list[int]:
    mc = (rw << 7) | (ch << 5) | (addr)
    cht = mtype << 6

    msq: list[int] = [mc, cht]

    if data is not None:
        msq.extend(data)

    cht |= msq_checksum(msq)
    msq[1] = cht

    return msq


def com_open() -> spidev.SpiDev:
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1000
    spi.mode = 0

    return spi


def com_close(spi: spidev.SpiDev, is_reset: bool = False) -> None:
    if is_reset:
        ltc2874_reset(spi)

    spi.close()


def com_status(spi: spidev.SpiDev) -> bool:
    enl1 = ltc2874_reg_read(spi, 0x0E)

    return enl1 == 0x11


def com_start(spi: spidev.SpiDev) -> serial.Serial:
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


def com_stop(spi: spidev.SpiDev, ser: serial.Serial | None = None, is_power_off: bool = False) -> None:
    if ser is not None:
        ser.close()

    # Drive disable
    ltc2874_reg_write(spi, 0x0D, 0x00)

    if is_power_off:
        # Power off
        logging.info("***** Power-Off IO-Link ****")
        ltc2874_reg_write(spi, 0x0E, 0x00)


def com_write(spi: spidev.SpiDev, ser: serial.Serial, byte_list: list[int]) -> None:
    # Drive enable
    ltc2874_reg_write(spi, 0x0D, 0x01)

    dump_byte_list("COM SEND", byte_list)

    ser.write(bytes(byte_list))
    ser.flush()

    # Drive disable
    ltc2874_reg_write(spi, 0x0D, 0x00)


def com_read(spi: spidev.SpiDev, ser: serial.Serial, length: int) -> list[int]:  # noqa: ARG001
    recv = ser.read(length)
    byte_list = list(recv)

    dump_byte_list("COM RECV", byte_list)

    return byte_list


def dir_param_read(spi: spidev.SpiDev, ser: serial.Serial, addr: int) -> int:
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
        raise SensorCommunicationError("response is too short")
    elif data[1] != msq_checksum([data[0]]):  # noqa:RET506
        raise SensorCRCError("checksum unmatch")

    return data[0]


def dir_param_write(spi: spidev.SpiDev, ser: serial.Serial, addr: int, value: int) -> None:
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
        raise SensorCommunicationError("response is too short")
    elif data[0] != msq_checksum([]):  # noqa: RET506
        raise SensorCRCError("checksum unmatch")


def isdu_req_build(index: int, length: int) -> list[list[int]]:
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


def isdu_res_read(spi: spidev.SpiDev, ser: serial.Serial, flow: int) -> int:
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
        raise SensorCommunicationError("response is too short")
    if data[1] != msq_checksum([data[0]]):
        raise SensorCRCError("checksum unmatch")

    return data[0]


def isdu_read(spi: spidev.SpiDev, ser: serial.Serial, index: int, data_type: int) -> str | int | list[int]:  # noqa: PLR0912, C901
    logging.debug("***** CALL: isdu_read(index: 0x%02X) ****", (index))
    length = 3

    isdu_req = isdu_req_build(index, length)

    for msq in isdu_req:
        com_write(spi, ser, msq)
        data = com_read(spi, ser, 4)

    chk = 0x00
    flow = 1
    data_list: list[int] = []
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
            raise SensorCommunicationError("ERROR response")
        else:
            raise SensorCommunicationError(f"INVALID response: {pprint.pformat(header)}")

    for _ in range(remain - 1):
        res = isdu_res_read(spi, ser, flow & 0xF)
        data_list.append(res)
        flow += 1
        chk ^= res

    chk ^= isdu_res_read(spi, ser, flow)

    if chk != 0x00:
        raise SensorCRCError("ISDU checksum unmatch")

    if data_type == DATA_TYPE_STRING:
        return bytes(data_list).decode("utf-8")
    elif data_type == DATA_TYPE_UINT16:
        return int.from_bytes(data_list, byteorder="big")
    else:
        return data_list
