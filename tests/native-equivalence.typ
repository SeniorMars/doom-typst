// Optional differential check against a previous build, supplied explicitly:
// typst compile --root . --input reference=/build/previous.wasm \
//   tests/native-equivalence.typ build/equivalence.pdf
#import "../engine/doom.typ": advance, info, framebuffer
#{
  let reference = plugin(sys.inputs.at("reference"))
  let candidate = plugin(sys.inputs.at("candidate", default: "../engine/doom.wasm"))
  let wad = read("../assets/doom1.wad", encoding: none)
  let new-game(map: 1) = plugin.transition(candidate.init, wad, bytes((1, 1, map, 1)))
  let old-game(map: 1) = plugin.transition(reference.init, wad, bytes((1, 1, map, 1)))
  let check(old, new) = {
    assert.eq(info(new), info(old), message: "Game state differs from reference")
    assert.eq(framebuffer(new), framebuffer(old), message: "Pixels differ from reference")
  }
  // View turns, weapons, automap, and menus on every available shareware map.
  for map in range(1, 10) {
    let old = old-game(map: map)
    let new = new-game(map: map)
    check(old, new)
    for actions in ("jjjjwwwwffffxxxxxxxx", "m", "m", "p", "p") {
      old = advance(old, actions)
      new = advance(new, actions)
      check(old, new)
    }
  }
  // Check intermediate frames, including combat/palette changes, doors, exit,
  // intermission, and the next level, rather than just the final state.
  let old = old-game()
  let new = new-game()
  let trace = read("fixtures/e1m1.txt").trim() + "x"*35 + "fxxf" + "x"*200
  for start in range(0, trace.len(), step: 14) {
    let actions = trace.slice(start, calc.min(start + 14, trace.len()))
    old = advance(old, actions)
    new = advance(new, actions)
    check(old, new)
  }
  assert.eq(info(new).map, 2)
  [Reference engine state and framebuffer comparisons passed.]
}
