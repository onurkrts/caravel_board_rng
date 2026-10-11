#ifndef RNG_COMMON_H
#define RNG_COMMON_H

#include <defs.h>
#include "swrng.h"

#define APP_SUITE 0     /* selftest, benchmark, verify stream, then random stream */
#define APP_NIST  1     /* selftest, then random stream only */

#ifndef APP
#define APP APP_SUITE
#endif

#define SUITE_FULL_SAMPLES 20000
#define SUITE_FULL_DECIM   10
#define BENCH_N            1024

#define LA_CLK (1u << 0)
#define LA_RST (1u << 1)

#define PKT_FULL     0x01
#define PKT_LSB      0x02
#define SRC_SINGLE   0x00
#define SRC_DOUBLE   0x20
#define SRC_SOFTWARE 0x40

static void rng_init(void);
static void rng_reset(void);
static void rng_read(uint32_t *x, uint32_t *y, uint32_t *z);
static void rng_step(void);
static int rng_selftest(void);
static void rng_bench(void);

/* ---------------------------------------------------------------- uart */

static void uart_putc(char c)
{
    while (reg_uart_txfull == 1);
    reg_uart_data = c;
}

static void putchar(char c)
{
    if (c == '\n') uart_putc('\r');
    uart_putc(c);
}

static void print(const char *p)
{
    while (*p) putchar(*p++);
}

static void print_hex(uint32_t v, int digits)
{
    for (int i = digits - 1; i >= 0; i--) {
        uint32_t n = (v >> (i * 4)) & 0xF;
        putchar(n < 10 ? '0' + n : 'a' + n - 10);
    }
}

static void print_dec(uint32_t v)
{
    static const uint32_t p10[] = {1000000000u, 100000000u, 10000000u, 1000000u,
                                   100000u, 10000u, 1000u, 100u, 10u, 1u};
    int started = 0;
    for (int i = 0; i < 10; i++) {
        int d = 0;
        while (v >= p10[i]) { v -= p10[i]; d++; }
        if (d || started || i == 9) { putchar('0' + d); started = 1; }
    }
}

static void print_xyz(uint32_t x, uint32_t y, uint32_t z)
{
    print_hex(x, 8); putchar(' ');
    print_hex(y, 8); putchar(' ');
    print_hex(z, 8);
}

static int check(const char *label, uint32_t x, uint32_t y, uint32_t z,
                 uint32_t ex, uint32_t ey, uint32_t ez)
{
    print(label);
    print_xyz(x, y, z);
    if (x == ex && y == ey && z == ez) {
        print("  OK\n");
        return 1;
    }
    print("  FAIL (expected ");
    print_xyz(ex, ey, ez);
    print(")\n");
    return 0;
}

/* ---------------------------------------------------------------- timer */

static void delay(uint32_t d)
{
    reg_timer0_config = 0;
    reg_timer0_data = d;
    reg_timer0_config = 1;
    reg_timer0_update = 1;
    while (reg_timer0_value > 0) reg_timer0_update = 1;
}

static void timer_start(void)
{
    reg_timer0_config = 0;
    reg_timer0_data = 0xFFFFFFFF;
    reg_timer0_data_periodic = 0;
    reg_timer0_config = 1;
}

static uint32_t timer_cycles(void)
{
    reg_timer0_update = 1;
    return 0xFFFFFFFF - reg_timer0_value;
}

/* ---------------------------------------------------------------- clock */

static void clock_setup(void)
{
    reg_hkspi_pll_ena = 0;      /* 10 MHz crystal, UART 9600 baud */
    reg_hkspi_pll_bypass = 1;
}

/* ---------------------------------------------------------------- io / logic analyzer */

static void io_setup(void)
{
    reg_gpio_mode1 = 1;
    reg_gpio_mode0 = 0;
    reg_gpio_ien = 1;
    reg_gpio_oe = 1;
#ifndef SKIP_GPIO_CONFIG
    reg_mprj_io_6 = GPIO_MODE_MGMT_STD_OUTPUT;
    reg_mprj_io_5 = GPIO_MODE_MGMT_STD_INPUT_NOPULL;
    reg_mprj_io_4 = GPIO_MODE_MGMT_STD_INPUT_NOPULL;
    reg_mprj_io_3 = GPIO_MODE_MGMT_STD_INPUT_NOPULL;
    reg_mprj_io_2 = GPIO_MODE_MGMT_STD_INPUT_NOPULL;
    reg_mprj_io_1 = GPIO_MODE_MGMT_STD_OUTPUT;
    reg_mprj_xfer = 1;
    while (reg_mprj_xfer == 1);
#endif
    reg_uart_enable = 1;
}

static uint32_t la3_out;

static inline void la3_write(uint32_t v)
{
    la3_out = v;
    reg_la3_data = v;
}

static inline void clk_pulse(void)
{
    la3_write(la3_out | LA_CLK);
    la3_write(la3_out & ~LA_CLK);
}

static inline void la_read(uint32_t *x, uint32_t *y, uint32_t *z)
{
    *x = reg_la0_data_in;
    *y = reg_la1_data_in;
    *z = reg_la2_data_in;
}

static void la_setup(uint32_t la3_idle)
{
    reg_la0_oenb = reg_la0_iena = 0;
    reg_la1_oenb = reg_la1_iena = 0;
    reg_la2_oenb = reg_la2_iena = 0;
    la3_write(la3_idle);
    reg_la3_oenb = reg_la3_iena = LA_CLK | LA_RST;
}

/* ---------------------------------------------------------------- streaming */

static uint8_t xsum;

static inline void send_byte(uint8_t b)
{
    xsum ^= b;
    uart_putc((char)b);
}

static inline void send_u32(uint32_t v)
{
    send_byte(v);
    send_byte(v >> 8);
    send_byte(v >> 16);
    send_byte(v >> 24);
}

/* Packet: 'R' 'N' 'G' type decim 0 seq[4] payload[192] xor[1]
 * FULL: 16 x (x,y,z) 32-bit little endian, LSB: 64 x (x,y,z) low bytes.
 * packets == 0 streams forever. */
static void stream(uint8_t type, uint32_t packets, int decim)
{
    int per_packet = (type & PKT_FULL) ? 16 : 64;
    uint32_t seq = 0, x, y, z;

    rng_reset();
    for (uint32_t p = 0; packets == 0 || p < packets; p++) {
        uart_putc('R'); uart_putc('N'); uart_putc('G');
        uart_putc(type);
        uart_putc(decim);
        uart_putc(0);
        uart_putc(seq); uart_putc(seq >> 8); uart_putc(seq >> 16); uart_putc(seq >> 24);
        xsum = 0;
        for (int i = 0; i < per_packet; i++) {
            rng_read(&x, &y, &z);
            if (type & PKT_FULL) {
                send_u32(x); send_u32(y); send_u32(z);
            } else {
                send_byte(x); send_byte(y); send_byte(z);
            }
            for (int k = 0; k < decim; k++) rng_step();
        }
        uart_putc(xsum);
        seq += per_packet;
        reg_gpio_out = (seq >> 8) & 1;
    }
}

/* ---------------------------------------------------------------- benchmark */

static volatile uint32_t sink;

static void bench_line(const char *name, uint32_t cycles)
{
    print("BENCH,");
    print(name);
    putchar(',');
    print_dec(cycles);
    putchar(',');
    print_dec(BENCH_N);
    putchar('\n');
}

static void bench_hardware(const char *read_name)
{
    uint32_t c, acc = 0, x, y, z;

    rng_reset();
    timer_start();
    for (int i = 0; i < BENCH_N; i++) {
        rng_read(&x, &y, &z);
        acc ^= x ^ y ^ z;
    }
    c = timer_cycles();
    sink = acc;
    bench_line(read_name, c);
}

static void bench_software(void)
{
    uint32_t c, acc = 0;
    xorshift_t xs;
    state_t s;

    timer_start();
    for (int i = 0; i < BENCH_N; i++) acc ^= i;
    c = timer_cycles();
    sink = acc;
    bench_line("loop-overhead", c);

    xorshift_init(&xs);
    timer_start();
    for (int i = 0; i < BENCH_N; i++)
        acc ^= xorshift_next(&xs) ^ xorshift_next(&xs) ^ xorshift_next(&xs);
    c = timer_cycles();
    sink = acc;
    bench_line("sw-xorshift32", c);

    single_init(&s);
    timer_start();
    for (int i = 0; i < BENCH_N; i++) {
        single_step(&s);
        acc ^= s.x ^ s.y ^ s.z;
    }
    c = timer_cycles();
    sink = acc;
    bench_line("sw-single-attractor", c);

    double_init(&s);
    timer_start();
    for (int i = 0; i < BENCH_N; i++) {
        double_step(&s);
        acc ^= s.x ^ s.y ^ s.z;
    }
    c = timer_cycles();
    sink = acc;
    bench_line("sw-double-attractor", c);
}

static void crosscheck(void (*init)(state_t *), void (*step)(state_t *))
{
    uint32_t x, y, z;
    state_t s;
    int ok = 1;

    init(&s);
    rng_reset();
    for (int i = 0; i < 1024 && ok; i++) {
        rng_read(&x, &y, &z);
        ok = x == s.x && y == s.y && z == s.z;
        step(&s);
        rng_step();
    }
    print(ok ? "CROSSCHECK sw==hw OK\n" : "CROSSCHECK sw==hw FAIL\n");
}

/* ---------------------------------------------------------------- main */

static void rng_main(const char *name, uint8_t source)
{
    clock_setup();
    rng_init();
    rng_reset();
    delay(2000000);

    print("\n== ");
    print(name);
    print(" ==\n");
    print(rng_selftest() ? "SELFTEST PASS\n" : "SELFTEST FAIL\n");

#if APP == APP_SUITE
    print("BENCH,source,cycles,samples\n");
    rng_bench();
    bench_software();
    print("BENCH,end,0,0\n");
    print("STAGE,full\n");
    stream(PKT_FULL | source, SUITE_FULL_SAMPLES / 16, SUITE_FULL_DECIM);
    print("\nSTAGE,lsb\n");
    stream(PKT_LSB | source, 0, 1);
#else
    print("STAGE,lsb\n");
    stream(PKT_LSB | source, 0, 1);
#endif
}

#endif
