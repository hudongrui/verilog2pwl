VERILOG_FILE=top.v
VCD_FILE=pattern.vcd

.PHONY: vcd2pwl debug clean

debug:
	@./vcd2pwl --debug -i ${VERILOG_FILE}

clean:
	@rm -f *.pwl *.vcd *.log *.out
