// Alternate cache build. Compare cached frames with independent full replay.
// typst compile --root . tests/replay-cache.typ build/replay-cache.pdf
#{
  let candidate = plugin(sys.inputs.at("candidate", default: "../build/doom-cache.wasm"))
  let reference = plugin("../engine/doom.wasm")
  let wad = read("../assets/freedoom1.wad", encoding: none)
  let count = 0
  for config in ((3, 1, 1, 4), (1, 1, 2, 1), (5, 2, 1, 4)) {
    let cached = plugin.transition(candidate.init, wad, bytes(config))
    let base = plugin.transition(reference.init, wad, bytes(config))
    let histories = ("", "w", "ww", "wwf", "wwfx", "ww", "s", "", "p", "pi", "pic", "pccc", "m", "mm", "wwwwjjffex"*10)
    for (i, history) in histories.enumerate() {
      // Unknown bytes do not advance Doom. A unique suffix defeats Typst's
      // result memoization, forcing even repeated histories through C.
      let input = bytes(history + "?"*(i+1))
      let expected = plugin.transition(base.advance, input).frame()
      assert.eq(cached.cached_frame(input), expected,
        message: "Cache mismatch for configuration " + repr(config) + " input " + repr(history))
      count += 1
    }
    // Exact-prefix hits after the final reset.
    let history = "wwwwjjffex"*10 + "?"*histories.len()
    for extra in ("w", "ww", "www", "wwww") {
      let input = bytes(history + extra)
      assert.eq(cached.cached_frame(input), plugin.transition(base.advance, input).frame())
      count += 1
    }
  }
  let cached = plugin.transition(candidate.init, wad, bytes((2, 1, 1, 4)))
  let base = plugin.transition(reference.init, wad, bytes((2, 1, 1, 4)))
  let trace = "wwwwjjffex"*32
  let histories = (trace.slice(0,15), trace.slice(0,16), trace.slice(0,17), trace, trace.slice(0,319), trace + "w", trace.slice(0,318)+"ss",
    trace.slice(0,255), trace.slice(0,256), trace.slice(0,257),
    "s" + trace.slice(1), trace + "ww", "pccc" + trace, "", trace,
    "wwwwjjffex"*400)
  for (i, history) in histories.enumerate() {
    let input = bytes(history + "?"*(i+1))
    assert.eq(cached.cached_frame(input), plugin.transition(base.advance,input).frame(),
      message: "Checkpoint restore differs at case " + str(i))
    count += 1
  }
  let cached = plugin.transition(candidate.init, wad, bytes((3, 1, 2, 4)))
  let base = plugin.transition(reference.init, wad, bytes((3, 1, 2, 4)))
  let trace = "wwwwjjffex"*40
  for (i, length) in (32, 48, 64, 80, 96, 112, 128, 144, 47, 79, 143, 31, 145).enumerate() {
    let input = bytes(trace.slice(0,length) + "?"*(i+1))
    assert.eq(cached.cached_frame(input), plugin.transition(base.advance,input).frame(),
      message: "Delta rewind differs at case " + str(i))
    count += 1
  }
  [#count cached frames match fresh full replay.]
}
