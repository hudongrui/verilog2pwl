#!/bin/python3
# -*- coding: utf-8 -*-
################################
# File Name   : vcd2pwl
# Author      : dongruihu
# Created at  : 2025-08-25 11:05:02
# Description:
#   Dump vcd waveform to PWL (Piecewise Linear) format
#################################
import os
import sys
import click
import logging
import colorlog
from pathlib import Path
from dataflow.types import *
from dataflow.parser import VCDParser


def setup_logger(log_file=f'vcd2pwl.log', level=logging.INFO):
    stdout_handler = colorlog.StreamHandler()
    stdout_handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s [%(asctime)s] | %(levelname)s | %(message)s', "%Y-%m-%d %H:%M:%S"))
    # '%(log_color)s [%(asctime)s] | %(levelname)s | %(funcName)s | %(message)s', "%Y-%m-%d %H:%M:%S"))

    file_handler = logging.FileHandler(log_file, mode='w')
    formatter = logging.Formatter('[%(asctime)s] | %(levelname)s | %(message)s', "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("main")
    logger.handlers.clear()
    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)
    logger.setLevel(level)

    return logger

logger = setup_logger()


# Comand-line Tool
@click.command()
@click.option('--debug/--no-debug', default=False)
@click.option('--input_file', '-i', nargs=1, required=True, help='Specify input filepath.')
@click.option('--output_file', '-o', nargs=1, required=False, default=None, help='Specify output filepath.')
@click.option('--trf', nargs=1, required=False, default=0, help='Transition rise/fall time for signals.')
@click.option('--tcrf', nargs=1, required=False, default=0, help='Transition rise/fall time for CLK signal.')
def dump(debug: bool, input_file: str, output_file: str, trf: int, tcrf: int):
    """
    A command-line tool to convert Value Change Dump to Piece-Wise Linear for SPICE.

    \tVersion: 1.0.2 | Date: 2025-09-29

    \tAuthor: dongruihu | dongruihu@picoheart.com

    For details, see reference: https://picoheart.feishu.cn/docx/NFtFd8JhqoczhAxp14OcfrY8nZc

    Copyright © 2025 ByteDance. All rights reserved.
    """
    global logger
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if Path(input_file).suffix != '.vcd':
        logger.error('Not a VCD file.')

    if not output_file:
        output_file = f'{Path(input_file).stem}.pwl'
    elif os.path.isfile(output_file):  # TODO
        pass

    parser = VCDParser()
    expr = {
            "trf": trf,
            "tcrf": tcrf
    }

    with open(input_file, 'rb') as f:
        vcd = parser.parse(f)

    vcd.export_pwl(output_file, expr=expr)
    logger.info(f'Generate piece-wise linear under: {output_file}')

if __name__ == "__main__":
    try:
        dump()
    except Exception as e:
        logger.error(f"Un-handled exception: {e}", exc_info=True)
        sys.exit(-1)
