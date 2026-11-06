// Real production sampler creation/invalidation, explicit mip reads and arrays.
// This synthetic Metal check is not a BOTW character-rendering certification.
#include "../nvn/nvn_mtl.m"
#include <assert.h>
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }

int main(void) { @autoreleasepool {
    g_dev = MTLCreateSystemDefaultDevice();
    if (!g_dev) { puts("SKIP sampler LOD GPU execution: no Metal device"); return 0; }
    unsetenv("DM_TEXTURE_DETAIL"); dm_tuning_init(NULL, 0, 1280, 720);
    NSError *error = nil;
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void sample_mips(texture2d_array<float> t[[texture(0)]], sampler s[[sampler(0)]], device float4 *out[[buffer(0)]], uint i[[thread_position_in_grid]])"
        "{out[i]=t.sample(s,float2(.5),i/4,level(float(i%4)));}";
    id<MTLLibrary> library = [g_dev newLibraryWithSource:source options:nil error:&error];
    if (!library) { fprintf(stderr, "sampler fixture compile: %s\n", error.description.UTF8String); return 1; }
    id<MTLComputePipelineState> pipeline = [g_dev newComputePipelineStateWithFunction:[library newFunctionWithName:@"sample_mips"] error:&error];
    assert(pipeline);
    MTLTextureDescriptor *descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:8 height:8 mipmapped:YES];
    descriptor.textureType = MTLTextureType2DArray; descriptor.arrayLength = 2;
    descriptor.storageMode = MTLStorageModeShared; descriptor.usage = MTLTextureUsageShaderRead;
    id<MTLTexture> texture = [g_dev newTextureWithDescriptor:descriptor]; assert(texture);
    uint8_t colors[8][4];
    for (unsigned slice = 0; slice < 2; slice++) for (unsigned level = 0; level < 4; level++) {
        unsigned i = slice * 4 + level, side = 8 >> level; uint8_t pixels[8 * 8 * 4];
        for (unsigned c = 0; c < 4; c++) colors[i][c] = c == 3 ? 255 : (uint8_t)(17 + i * 19 + c * 7);
        for (unsigned pixel = 0; pixel < side * side; pixel++) memcpy(pixels + pixel * 4, colors[i], 4);
        [texture replaceRegion:MTLRegionMake2D(0, 0, side, side) mipmapLevel:level slice:slice withBytes:pixels bytesPerRow:side * 4 bytesPerImage:side * side * 4];
    }
    id<MTLBuffer> output = [g_dev newBufferWithLength:8 * 4 * sizeof(float) options:MTLResourceStorageModeShared]; assert(output);
    id<MTLCommandQueue> queue = [g_dev newCommandQueue]; assert(queue);
    samp_par parameters = {.minf = 5, .magf = 1, .lod_max = 3, .aniso = 8};
    mtl_reg_samp(1, &parameters); g_fence = 41; g_done = 0;
    const int modes[] = {0, 1, 2, 0};
    for (unsigned trial = 0; trial < sizeof modes / sizeof *modes; trial++) {
        int q = modes[trial]; uint64_t generation = g_reg_gen;
        assert(dm_tuning_set("DM_TEXTURE_DETAIL", q)); dm_tuning_tick(1000000000ull + trial * 17000000ull, 6, 17, 0, 0);
        quality_samplers_refresh();
        if (trial) { assert(!g_sview[1] && !g_srid[1]); assert(g_reg_gen > generation); }
        os_unfair_lock_lock(&g_rmu); id<MTLSamplerState> sampler = samp_by_id(1); os_unfair_lock_unlock(&g_rmu); assert(sampler);
        id<MTLCommandBuffer> command = [queue commandBuffer]; id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        [encoder setComputePipelineState:pipeline]; [encoder setTexture:texture atIndex:0];
        [encoder setSamplerState:sampler atIndex:0]; [encoder setBuffer:output offset:0 atIndex:0];
        [encoder dispatchThreads:MTLSizeMake(8, 1, 1) threadsPerThreadgroup:MTLSizeMake(8, 1, 1)];
        [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
        assert(command.status == MTLCommandBufferStatusCompleted);
        const float *actual = output.contents;
        for (unsigned i = 0; i < 8; i++) for (unsigned c = 0; c < 4; c++) assert(fabsf(actual[i * 4 + c] - colors[i][c] / 255.0f) < .001f);
    }
    assert(g_deferred.count == 3);
    for (NvDeferredRelease *entry in g_deferred) assert(entry->fence == 42 && entry->keep_resident);
    g_done = 41; defer_drain(); assert(g_deferred.count == 3);
    g_done = 42; defer_drain(); assert(!g_deferred.count);
    puts("PASS sampler LOD GPU: Original/2x/1x/Original, 4 explicit mips, 2 layers, descriptor invalidation and deferred lifetimes");
} return 0; }
