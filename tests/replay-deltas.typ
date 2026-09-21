// Exercise history eviction and branching. Also run with --replay-delta-bytes 64
// to force the oversized-patch fallback, or 65536 for a small history budget.
#{
  let engine = plugin(sys.inputs.at("candidate", default: "../build/doom-cache.wasm"))
  let reference = plugin("../engine/doom.wasm")
  let wad = read("../assets/freedoom1.wad", encoding: none)
  let config = bytes((3,1,1,1))
  let cache = plugin.transition(engine.init, wad, config)
  let base = plugin.transition(reference.init, wad, config)
  let expected = base
  let trace = "wwjjffex"*64
  for i in range(1,33) {
    expected = plugin.transition(expected.advance, bytes(trace.slice((i - 1) * 16, i * 16)))
    assert.eq(cache.cached_frame(bytes(trace.slice(0,i*16))), expected.frame())
  }
  for (i,n) in (495,479,463,127,511,63,500).enumerate() {
    let input=bytes(trace.slice(0,n)+"?"*(i+1))
    assert.eq(cache.cached_frame(input), plugin.transition(base.advance,input).frame())
  }
  [39 delta-history and fallback comparisons passed.]
}
