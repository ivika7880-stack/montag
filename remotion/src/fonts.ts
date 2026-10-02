// Public template: no bundled commercial font shipped with this repo.
// Point `brandFontFamily` at your own display font. Two ways:
//   1) Google font — see .claude/skills/remotion/rules/google-fonts.md
//   2) Local font — drop a .otf/.ttf into remotion/public and register it via
//      @font-face below (uncomment), then set brandFontFamily to its family name.
//
// Register via a CSS @font-face (not @remotion/fonts / FontFace.load): Remotion
// recycles the render tab under @remotion/media memory pressure, and font-load
// promises can hang on the recycled page. The CSS pipeline paints on every page
// with no promise to stall. Use a data URI or staticFile() as src.

export const brandFontFamily = "'Arial Narrow', 'Oswald', Impact, sans-serif";

// Example — local font from remotion/public/brandfont.otf:
//
// import { staticFile } from "remotion";
// if (typeof document !== "undefined") {
//   const style = document.createElement("style");
//   style.textContent =
//     `@font-face{font-family:"BrandFont";` +
//     `src:url("${staticFile("brandfont.otf")}") format("opentype");font-display:block;}`;
//   document.head.appendChild(style);
// }
// export const brandFontFamily = "BrandFont, sans-serif";
