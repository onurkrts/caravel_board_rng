/* Single-attractor chaotic RNG (github.com/onurkrts/RNG)
 * LA[31:0]=x  LA[63:32]=y  LA[95:64]=z  LA[96]=clk  LA[97]=rst (active low)
 */
#include "common.h"

static void rng_init(void)
{
    io_setup();
    la_setup(0);
}

static void rng_reset(void)
{
    la3_write(0);
    clk_pulse();
    clk_pulse();
    la3_write(LA_RST);
}

static void rng_read(uint32_t *x, uint32_t *y, uint32_t *z)
{
    la_read(x, y, z);
}

static void rng_step(void)
{
    clk_pulse();
}

static int rng_selftest(void)
{
    uint32_t x, y, z;
    int ok = 1;

    rng_reset();
    la_read(&x, &y, &z);
    ok &= check("reset    ", x, y, z, 0x00000000, 0x00400000, 0x00000000);
    clk_pulse();
    la_read(&x, &y, &z);
    ok &= check("step 1   ", x, y, z, 0x00010000, 0x00400000, 0xfffc0000);
    return ok;
}

static void rng_bench(void)
{
    bench_hardware("hw-single-read");
    crosscheck(single_init, single_step);
}

void main(void)
{
    rng_main("single-attractor chaotic RNG", SRC_SINGLE);
}
