#pragma once
#include <math.h>
// Body-to-start-frame quaternion; heading is relative, not magnetic north.
struct Orientation {
    float w=1, x=0, y=0, z=0, bx=0, by=0, bz=0;
    unsigned samples=0;
    bool ready=false;
    void update(float ax,float ay,float az,float gx,float gy,float gz,float dt) {
        if (!ready) {
            float a=sqrtf(ax*ax+ay*ay+az*az);
            if (fabsf(a-1)>0.08f || fabsf(gx)>15 || fabsf(gy)>15 || fabsf(gz)>15) {
                samples=0; bx=by=bz=0; return;
            }
            bx+=gx; by+=gy; bz+=gz;
            if (++samples==200) { bx/=samples; by/=samples; bz/=samples; ready=true; }
            return;
        }
        if (dt<=0 || dt>0.2f) return;
        const float rad=0.01745329252f;
        gx=(gx-bx)*rad; gy=(gy-by)*rad; gz=(gz-bz)*rad;
        float speed=sqrtf(gx*gx+gy*gy+gz*gz);
        if (speed<1e-6f) return;
        float h=speed*dt*0.5f, k=sinf(h)/speed;
        float dw=cosf(h), dx=gx*k, dy=gy*k, dz=gz*k;
        float nw=w*dw-x*dx-y*dy-z*dz;
        float nx=w*dx+x*dw+y*dz-z*dy;
        float ny=w*dy-x*dz+y*dw+z*dx;
        float nz=w*dz+x*dy-y*dx+z*dw;
        float n=sqrtf(nw*nw+nx*nx+ny*ny+nz*nz);
        w=nw/n; x=nx/n; y=ny/n; z=nz/n;
    }
};
