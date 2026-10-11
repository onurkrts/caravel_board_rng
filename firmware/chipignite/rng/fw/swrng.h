#ifndef RNG_SWRNG_H
#define RNG_SWRNG_H

#include <stdint.h>

#define XS_SEED 2463534242u

static inline uint32_t sra(uint32_t v, int s)
{
    return (uint32_t)((int32_t)v >> s);
}

typedef struct { uint32_t s; } xorshift_t;

static inline void xorshift_init(xorshift_t *r)
{
    r->s = XS_SEED;
}

static inline uint32_t xorshift_next(xorshift_t *r)
{
    uint32_t x = r->s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    r->s = x;
    return x;
}

typedef struct { uint32_t x, y, z; } state_t;

static inline void single_init(state_t *s)
{
    s->x = 0;
    s->y = 1u << 22;
    s->z = 0;
}

static inline void single_step(state_t *s)
{
    uint32_t x = s->x, y = s->y, z = s->z;
    uint32_t by = (!(y >> 31) && ((y >> 22) & 0x1FF)) ? (y << 2) : 0;
    uint32_t zd = z + x + by;
    s->x = x + sra(y, 6);
    s->y = y + sra(z, 6);
    s->z = z - sra(zd, 6);
}

static inline uint32_t sawtooth(uint32_t f, uint32_t u, uint32_t l)
{
    uint32_t hi = (f >> 26) & 0x3F;
    uint32_t xhigh = (hi - ((((l >> 3) & 1) << 5) | ((l & 0xF) << 1) | 1)) & 0x3F;
    uint32_t x26n = ((f >> 26) & 1) ? 0 : 0x3F;
    uint32_t u2 = (u >> 2) & 1;
    uint32_t xu = (hi - ((u2 << 5) | (u2 << 4) | ((u & 7) << 1) | 1)) & 0x3F;
    uint32_t out = (xhigh & 0x20) ? xhigh : ((xu & 0x20) ? x26n : xu);
    return (out << 26) | (f & 0x3FFFFFF);
}

static inline void double_init(state_t *s)
{
    s->x = 0xde78d681u;
    s->y = 0xfeee4640u;
    s->z = 0xfe8e511bu;
}

static inline void double_step(state_t *s)
{
    uint32_t x = s->x, y = s->y, z = s->z;
    uint32_t xo = sawtooth(x, 0x4, 0xB);
    uint32_t zd1 = xo + y + z;
    uint32_t zd = zd1 - sra(zd1, 4);
    s->x = x + sra(y, 3);
    s->y = y + sra(z, 3);
    s->z = z - sra(zd, 3);
}

#endif
