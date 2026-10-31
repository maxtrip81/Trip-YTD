// Disegna l'icona di Trip YTD (stesse forme di icon.svg) in un PNG 1024×1024 trasparente.
// Uso: swift make_icon.swift <output.png>
import AppKit

let size = 1024
let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon_1024.png"

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let ctx = NSGraphicsContext.current!.cgContext

// coordinate come nell'SVG (origine in alto a sinistra)
ctx.translateBy(x: 0, y: CGFloat(size))
ctx.scaleBy(x: 1, y: -1)

let body = CGPath(roundedRect: CGRect(x: 100, y: 100, width: 824, height: 824),
                  cornerWidth: 185, cornerHeight: 185, transform: nil)
ctx.addPath(body)
ctx.clip()
let colors = [NSColor(srgbRed: 0x7c / 255, green: 0x3a / 255, blue: 0xed / 255, alpha: 1).cgColor,
              NSColor(srgbRed: 0xdb / 255, green: 0x27 / 255, blue: 0x77 / 255, alpha: 1).cgColor]
let gradient = CGGradient(colorsSpace: CGColorSpace(name: CGColorSpace.sRGB), colors: colors as CFArray,
                          locations: [0, 1])!
ctx.drawLinearGradient(gradient, start: CGPoint(x: 100, y: 100), end: CGPoint(x: 924, y: 924), options: [])
ctx.resetClip()

ctx.setFillColor(NSColor.white.cgColor)
for (x, y, h) in [(212, 462, 100), (304, 382, 260), (664, 382, 260), (756, 462, 100)] {
    ctx.addPath(CGPath(roundedRect: CGRect(x: x, y: y, width: 56, height: h),
                       cornerWidth: 28, cornerHeight: 28, transform: nil))
}
ctx.fillPath()

ctx.setStrokeColor(NSColor.white.cgColor)
ctx.setLineWidth(64)
ctx.setLineCap(.round)
ctx.setLineJoin(.round)
ctx.move(to: CGPoint(x: 512, y: 270))
ctx.addLine(to: CGPoint(x: 512, y: 680))
ctx.move(to: CGPoint(x: 430, y: 598))
ctx.addLine(to: CGPoint(x: 512, y: 680))
ctx.addLine(to: CGPoint(x: 594, y: 598))
ctx.strokePath()

NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
