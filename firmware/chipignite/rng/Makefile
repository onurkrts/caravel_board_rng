# caravel_board/firmware/chipignite/rng
#
#   make flash DESIGN=single              suite: selftest, benchmark, verification, random bytes
#   make flash DESIGN=double APP=nist     random byte stream only
#   make sim                              RTL vs. model check (Icarus Verilog)

CHIP      ?= ..
DESIGN    ?= single
APP       ?= suite
EXTRA     ?=
TOOLCHAIN ?= /usr/bin/riscv64-unknown-elf-

CC    := $(TOOLCHAIN)gcc
MARCH := $(shell $(CC) -march=rv32i_zicsr -mabi=ilp32 -x c -c -o /dev/null /dev/null 2>/dev/null && echo rv32i_zicsr || echo rv32i)

BUILD := build
ELF   := $(BUILD)/$(DESIGN)_$(APP).elf
HEX   := $(BUILD)/$(DESIGN)_$(APP).hex

CFLAGS  := -I$(CHIP) -I$(CHIP)/generated -O1 -mabi=ilp32 -march=$(MARCH) -D__vexriscv__ \
           -ffreestanding -nostdlib -DAPP=APP_$(shell echo $(APP) | tr a-z A-Z) $(EXTRA)
LDFLAGS := -Wl,-Bstatic,-T,$(CHIP)/sections.lds,--strip-debug

hex: $(HEX)

$(HEX): FORCE
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $(ELF) $(CHIP)/crt0_vex.S $(CHIP)/isr.c fw/$(DESIGN).c
	$(TOOLCHAIN)objdump -D $(ELF) > $(BUILD)/$(DESIGN)_$(APP).lst
	$(TOOLCHAIN)objcopy -O verilog $(ELF) $@
	sed -i 's/@1000/@0000/g' $@

flash: $(HEX)
	python3 $(CHIP)/util/caravel_hkflash.py $(HEX)

sim:
	@mkdir -p $(BUILD)
	iverilog -o $(BUILD)/tb_single sim/tb_single.v sim/rtl_single.v
	cd $(BUILD) && vvp -n tb_single
	python3 host/models.py check single $(BUILD)/rtl_single.txt
	iverilog -o $(BUILD)/tb_double sim/tb_double.v sim/rtl_double.v
	cd $(BUILD) && vvp -n tb_double
	python3 host/models.py check double $(BUILD)/rtl_double.txt

clean:
	rm -rf $(BUILD)

FORCE:
.PHONY: hex flash sim clean FORCE
