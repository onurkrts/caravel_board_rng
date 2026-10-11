# rng

Firmware and host tools for two SKY130 chaotic random number generator chips on the Caravel
evaluation board, compared with a software RNG running on the same RISC-V core.

| Source     | Chip                                                   | System                                            | Interface                      |
|------------|--------------------------------------------------------|---------------------------------------------------|--------------------------------|
| `single`   | MPW-5, [onurkrts/RNG](https://github.com/onurkrts/RNG)               | single-attractor jerk, a=4, h=2^-6, Q10.22        | LA, rst active low             |
| `double`   | MPW-6, [onurkrts/RNG-SCROLL](https://github.com/onurkrts/RNG-SCROLL) | double-attractor sawtooth, a=15/16, h=2^-3, Q6.26 | LA + Wishbone, rst active high |
| `software` | any chip                                               | xorshift32 on the Caravel VexRiscv                | -                              |

```
fw/      firmware: common.h (shared), swrng.h (C models), single.c, double.c, software.c
host/    models.py, suite.py, collect.py, nist.py, compare.py, analyze.py
sim/     chip RTL and Icarus Verilog testbenches
```

The cores are clocked through LA[96], one Euler step per pulse, so every sample read from the chip
can be checked against the bit-exact models in `host/models.py` and `fw/swrng.h`.

## Setup

This folder lives in `caravel_board/firmware/chipignite/rng` and uses the Caravel headers and
`util/caravel_hkflash.py` from the parent directory. Tested on Ubuntu 20.04 (WSL with `usbipd`).

```bash
sudo apt install gcc-riscv64-unknown-elf iverilog
python3 -m venv ~/caravel-venv && source ~/caravel-venv/bin/activate
pip install numpy matplotlib pyserial pyftdi scikit-image
cd caravel_board/firmware/chipignite/rng
python3 host/nist.py setup        # NIST STS 2.1.2 into ~/nist-sts (once)
make sim                          # optional: RTL vs. model, 200000 steps per design
```

Every flash: remove J2, `sudo chmod -R a+rw /dev/bus/usb/`, `make flash ...`, put J2 back on
(J2 routes the UART to the FT232H). Everything runs at 10 MHz, UART 9600 8N1.

## Firmware

```bash
make flash DESIGN=single              # APP=suite (default)
make flash DESIGN=double APP=nist
```

| `APP`   | After reset                                                                          |
|---------|--------------------------------------------------------------------------------------|
| `suite` | selftest, benchmark, sw/hw crosscheck, 20000 full samples (every 10th step), then random bytes |
| `nist`  | selftest, then random bytes                                                          |

Random bytes are the low bytes of x, y and z at every Euler step, without post-processing,
sent in 203-byte packets (`RNG`, type, decimation, sequence number, 192 data bytes, XOR checksum).

## 1. Suite (per source, about 25 min)

```bash
make flash DESIGN=single
python3 host/suite.py                 # put J2 on, press RESET
```

```
== summary: single ==
selftest    PASS
crosscheck  OK
verify      PASS
files       single_suite.log, bench_single.txt, single_full.npz, single_lsb.bin
```

Writes `data/NAME_suite.log`, `data/bench_NAME.txt`, `data/NAME_full.npz/.csv`,
`data/NAME_lsb.bin` (1 MB) and `figures/phase_NAME.pdf`. Repeat with `DESIGN=double` and
`DESIGN=software`.

## 2. NIST SP 800-22 (per source, 100 x 1 Mbit, about 4 h)

```bash
make flash DESIGN=single APP=nist
python3 host/collect.py --bytes 12500000 --out data/single_nist
python3 host/nist.py run data/single_nist.bin --name single
```

After all three sources:

```bash
python3 host/nist.py table results/nist_single.txt results/nist_double.txt results/nist_software.txt
```

`results/nist.csv` and `results/nist.tex` give PASS/FAIL per test, the worst pass proportion
(minimum 96/100) and the smallest p-value uniformity (>= 0.0001).

## 3. Comparison

```bash
python3 host/compare.py \
    --lsb single=data/single_lsb.bin double=data/double_lsb.bin software=data/software_lsb.bin \
    --bench data/bench_single.txt data/bench_double.txt data/bench_software.txt \
    --image moon --out results
```

| Output             | Content                                                                                       |
|--------------------|-----------------------------------------------------------------------------------------------|
| `randomness.*`     | frequency, block frequency, runs, cumulative sums (8 x 1 Mbit), byte chi-square, entropy, lag-1 correlation |
| `performance.*`    | VexRiscv cycles per 96-bit sample: reading the hardware core, xorshift32 and both chaotic systems in software |
| `encryption.*`     | Fisher-Yates permutation + XOR of a 256x256 image: entropy, chi-square, adjacent correlation, NPCR/UACI |
| `statistics.pdf`   | byte histograms and autocorrelation                                                           |
| `encryption.pdf`   | plain and encrypted images with histograms                                                    |

`--image` accepts `moon`, `chelsea`, `coffee`, `camera`, `brick` (scikit-image) or a file path.

Phase portraits from the models, every Euler step:

```bash
python3 host/analyze.py single --n 20000 --skip 2000 --out figures/phase_single_model.pdf
```

## Troubleshooting

| Symptom                    | Fix                                                                               |
|----------------------------|-----------------------------------------------------------------------------------|
| `No matching FTDI devices` | remove J2; `usbipd attach --wsl --busid 1-1`; `sudo chmod -R a+rw /dev/bus/usb/` |
| `waiting for the board`    | J2 on? press RESET                                                                |
| no UART text at all        | `make flash ... EXTRA=-DSKIP_GPIO_CONFIG`                                         |
| garbage characters         | power-cycle the board                                                             |
