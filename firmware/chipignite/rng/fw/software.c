/* Software reference RNG: xorshift32 (Marsaglia, 2003) on the Caravel RISC-V.
 * One sample = three consecutive outputs. Works with any chip inserted.
 */
#include "common.h"

static xorshift_t xs;
static uint32_t sx, sy, sz;

static void rng_init(void)
{
    io_setup();
}

static void rng_step(void)
{
    sx = xorshift_next(&xs);
    sy = xorshift_next(&xs);
    sz = xorshift_next(&xs);
}

static void rng_reset(void)
{
    xorshift_init(&xs);
    rng_step();
}

static void rng_read(uint32_t *x, uint32_t *y, uint32_t *z)
{
    *x = sx;
    *y = sy;
    *z = sz;
}

static int rng_selftest(void)
{
    uint32_t x, y, z;
    int ok = 1;

    rng_reset();
    rng_read(&x, &y, &z);
    ok &= check("sample 0 ", x, y, z, 0x2b1f4d63, 0x94dacb7a, 0x7b0859a0);
    rng_step();
    rng_read(&x, &y, &z);
    ok &= check("sample 1 ", x, y, z, 0x77b0567e, 0xd28ab0e1, 0x164c87ea);
    return ok;
}

static void rng_bench(void)
{
}

void main(void)
{
    rng_main("software xorshift32 RNG", SRC_SOFTWARE);
}
