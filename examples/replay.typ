// Recorded ordinary inputs: E1M1 through its exit, then intermission and E1M2.
// Export at 72 PPI; displaying the pages at 10 fps gives 4x playback speed.
#import "../engine/doom.typ": new-game, advance, framebuffer
#set page(width: 320pt, height: 240pt, margin: 0pt, fill: black)
#{
  let game = new-game(read("../assets/doom1.wad", encoding: none), skill: 1, tics: 1)
  let actions = read("../tests/fixtures/e1m1.txt").trim() + "x" * 35 + "fxxf" + "x" * 200
  for start in range(0, actions.len(), step: 14) {
    if start > 0 { pagebreak() }
    game = advance(game, actions.slice(start, calc.min(start + 14, actions.len())))
    image(framebuffer(game), format: (encoding: "rgb8", width: 320, height: 200),
      width: 320pt, height: 240pt, fit: "stretch", scaling: "pixelated")
  }
}
