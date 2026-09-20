#import "../engine/doom.typ": new-game, advance, framebuffer
#set page(width: 640pt, height: 480pt, margin: 0pt)
#{
  let wad = read("../assets/doom1.wad", encoding: none)
  let base = new-game(wad)
  let scenes = (base, advance(base, "wwwwwwwwwwwwwwwwjjjjffff"), advance(base, "p"), new-game(wad, map: 2))
  for (i, game) in scenes.enumerate() {
    if i > 0 { pagebreak() }
    image(framebuffer(game), format: (encoding: "rgb8", width: 320, height: 200),
      width: 640pt, height: 480pt, fit: "stretch", scaling: "pixelated")
  }
}
