#!/usr/bin/python3
# -*- coding: utf-8 -*-
################################
# File Name   : verilog2pwl
# Author      : dongruihu
# Created at  : 2025-08-25 11:05:02
# Description:
#   Dump verilog testbench waveform to PWL (Piecewise Linear) format, using VCS

import os
import sys
import subprocess
import click
import logging
import colorlog
from pathlib import Path
from dataflow.types import *
from dataflow.parser import VCDParser
from dataflow.helper import parse_ast, run_command, safe_get_module_top
from pyverilog.vparser.parser import ParseError

def setup_logger(log_file=f'verilog2pwl.log', level=logging.INFO):
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


@click.command()
@click.option('--debug/--no-debug', default=False)
@click.option('--input_file', '-i', nargs=1, required=True, help='Specify input filepath.')
@click.option('--output_file', '-o', nargs=1, required=False, default=None, help='Specify output filepath.')
@click.option('--trf', nargs=1, required=False, default=0, help='Transition rise/fall time for signals.')
@click.option('--tcrf', nargs=1, required=False, default=0, help='Transition rise/fall time for CLK signal.')
def dump(debug: bool, input_file: str, output_file: str, trf: int, tcrf: int):
    """
    A command-line tool to convert Verilog Testbench to Piece-Wise Linear for SPICE.

    \tVersion: 1.0.2 | Date: 2025-09-29

    \tAuthor: dongruihu | dongruihu@picoheart.com
    """
    global logger
    file_stem = f'{Path(input_file).stem}'
    file_dir = f'{Path(input_file).parent}'

    logger = setup_logger(f'verilog2pwl.{file_stem}.log', level=logging.DEBUG if debug else logging.INFO)

    if Path(input_file).suffix != '.v':
        logger.error('Not a verilog file.')
        sys.exit(-1)

    try:
        ast, module_top = parse_ast([input_file])  # NOTE: Could be a list of files.
    except ParseError as e:
        logger.warning(f"Unable to parse input file with 'pyverilog' module: {e}")
        module_top = safe_get_module_top(input_file)  # Temp-workaround
        logger.info(f"Conservatively using module_top: {module_top}")

    if not output_file:
        output_file = f'{module_top}.pwl'
    elif os.path.isfile(output_file):
        pass

    # Dump vcd using VCS simulator
    parent_path = Path(__file__).resolve().parent
    proc = subprocess.run(f'{parent_path}/dump_vcd.sh {input_file} {module_top}', shell=True, text=True)
    _code = proc.returncode
    logger.info(proc.stdout)

    if _code != 0:
        logger.error(proc.stderr)
        logger.error(f'Failed to dump vcd from DUT verilog testbench. Exit code: {_code}')

    # Parse vcd
    parser = VCDParser()
    expr = {
        "trf": trf,
        "tcrf": tcrf
    }

    vcd_file = f'{file_dir}/{module_top}.vcd'
    with open(vcd_file, 'rb') as f:
        vcd = parser.parse(f)

    # Dump pwl
    vcd.export_pwl(output_file, expr=expr)
    logger.info(f'Generate piece-wise linear under: {output_file}')


########
# MAIN #
########
if __name__ == '__main__':
    dump()