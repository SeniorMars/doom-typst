#import "../engine/doom.typ": play, advance, info, framebuffer
#{
  // A complete E1M1 run using ordinary movement/fire/use inputs, without cheats
  // or save restoration. This trace is specific to skill 1 and one tic per key.
  let game = play(read("fixtures/e1m1.txt"), skill: 1, tics: 1)
  let state = info(game)
  assert.eq(state.state, 1, message: "Exit switch must enter intermission")
  assert.eq(state.map, 1)
  assert.eq(state.health, 63)
  assert.eq(state.kills, 2)
  assert.eq(framebuffer(game).len(), 320 * 200 * 3)
  let next = advance(game, "fxxf" + "x" * 200)
  assert.eq(info(next).state, 0)
  assert.eq(info(next).map, 2, message: "Intermission must lead to E1M2")
  assert.eq(framebuffer(next).len(), 320 * 200 * 3)
  [E1M1 exit and E1M2 progression checks passed.]
}
