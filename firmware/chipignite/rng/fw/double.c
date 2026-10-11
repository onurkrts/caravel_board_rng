/* Double-attractor chaotic RNG (github.com/onurkrts/RNG-SCROLL)
 * LA[31:0]=x  LA[63:32]=y  LA[95:64]=z  LA[96]=clk  LA[97]=rst (active high)
 * Wishbone @0x30000000: 04 x_init, 08 y_init, 0C z_init, 10 scroll, 14 en,
 *                       18 sample, 1C x_data, 20 y_data, 24 z_data
 */
#include "common.h"

#define WB(off)   (*(volatile uint32_t *)(0x30000000u + (off)))
#define WB_X_INIT WB(0x04)
#define WB_Y_INIT WB(0x08)
#define WB_Z_INIT WB(0x0C)
#define WB_SCROLL WB(0x10)
#define WB_EN     WB(0x14)
#define WB_SAMPLE WB(0x18)
#define WB_X_DATA WB(0x1C)
#define WB_Y_DATA WB(0x20)
#define WB_Z_DATA WB(0x24)

#define X_INIT 0xde78d681u
#define Y_INIT 0xfeee4640u
#define Z_INIT 0xfe8e511bu

static void rng_init(void)
{
    io_setup();
    la_setup(0);
    reg_wb_enable = 1;
}

static void rng_reset(void)
{
    la3_write(LA_RST);
    clk_pulse();
    la3_write(0);
}

static void wb_read(uint32_t *x, uint32_t *y, uint32_t *z)
{
    WB_SAMPLE = 1;
    *x = WB_X_DATA;
    *y = WB_Y_DATA;
    *z = WB_Z_DATA;
}

static void rng_read(uint32_t *x, uint32_t *y, uint32_t *z)
{
    wb_read(x, y, z);
}

static void rng_step(void)
{
    clk_pulse();
}

static int rng_selftest(void)
{
    uint32_t x, y, z;
    int ok = 1;

    ok &= check("wb init  ", WB_X_INIT, WB_Y_INIT, WB_Z_INIT, X_INIT, Y_INIT, Z_INIT);
    print("wb cfg   scroll=");
    print_hex(WB_SCROLL, 6);
    print(" en=");
    print_hex(WB_EN, 1);
    if (WB_SCROLL == 0x4d4c4b && WB_EN == 0x3) {
        print("  OK\n");
    } else {
        print("  FAIL (expected 4d4c4b / 3)\n");
        ok = 0;
    }
    rng_reset();
    la_read(&x, &y, &z);
    ok &= check("reset la ", x, y, z, X_INIT, Y_INIT, Z_INIT);
    clk_pulse();
    la_read(&x, &y, &z);
    ok &= check("step1 la ", x, y, z, 0xde569f49, 0xfec01063, 0xfe8f8e3c);
    wb_read(&x, &y, &z);
    ok &= check("step1 wb ", x, y, z, 0xde569f49, 0xfec01063, 0xfe8f8e3c);
    return ok;
}

static void rng_bench(void)
{
    bench_hardware("hw-double-read");
    crosscheck(double_init, double_step);
}

void main(void)
{
    rng_main("double-attractor chaotic RNG", SRC_DOUBLE);
}
