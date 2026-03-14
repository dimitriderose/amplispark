/** Shared image style options for style picker dropdowns. */
export const IMAGE_STYLE_GROUPS = [
  {
    label: 'Photography',
    options: [
      { value: 'photorealistic', label: 'Photorealistic', desc: 'Sharp, natural, professional camera look' },
      { value: 'editorial', label: 'Editorial', desc: 'Magazine-quality, soft diffused light' },
      { value: 'documentary', label: 'Documentary', desc: 'Candid, raw, photojournalism feel' },
      { value: 'cinematic', label: 'Cinematic', desc: 'Dramatic lighting, film grain, teal-orange' },
      { value: 'food-photo', label: 'Food Photo', desc: 'Overhead/45°, warm light, appetizing' },
      { value: 'product', label: 'Product', desc: 'Clean background, studio lighting, sharp detail' },
      { value: 'lifestyle', label: 'Lifestyle', desc: 'People in natural settings, golden hour' },
      { value: 'lo-fi', label: 'Lo-Fi', desc: 'Grain, desaturated, analog camera feel' },
    ],
  },
  {
    label: 'Illustration',
    options: [
      { value: 'illustration', label: 'Illustration', desc: 'Clean vector-like art, bold colors' },
      { value: 'hand-drawn', label: 'Hand-Drawn', desc: 'Visible brush strokes, organic, warm' },
      { value: 'anime', label: 'Anime', desc: 'Japanese animation style, vibrant colors' },
      { value: 'cartoon', label: 'Cartoon', desc: 'Bold outlines, bright colors, playful' },
      { value: 'watercolor', label: 'Watercolor', desc: 'Soft color bleeds, dreamy, artistic' },
      { value: 'pixel-art', label: 'Pixel Art', desc: 'Retro 8-bit/16-bit game aesthetic' },
      { value: 'risograph', label: 'Risograph', desc: 'Retro print look, halftone dots, 2-3 colors' },
    ],
  },
  {
    label: '3D & Futuristic',
    options: [
      { value: '3d-render', label: '3D Render', desc: 'Clean geometry, soft lighting, glass/metal' },
      { value: 'futuristic', label: 'Futuristic', desc: 'Neon accents, holographic, cyberpunk' },
      { value: 'retro-futurism', label: 'Retro-Futurism', desc: 'Chrome, neon, 80s sci-fi aesthetic' },
    ],
  },
  {
    label: 'Graphic Design',
    options: [
      { value: 'bold-minimal', label: 'Bold Minimal', desc: 'Strong focal point, max whitespace' },
      { value: 'maximalist', label: 'Maximalist', desc: 'Layered, dense, eclectic, bold colors' },
      { value: 'neo-brutalist', label: 'Neo-Brutalist', desc: 'Raw layout, oversized type, high contrast' },
      { value: 'mixed-media', label: 'Mixed Media', desc: 'Photo + illustration + texture collage' },
      { value: 'flat-design', label: 'Flat Design', desc: 'Solid colors, geometric, clean UI feel' },
      { value: 'glitch', label: 'Glitch', desc: 'Digital distortion, RGB shift, cyberpunk' },
    ],
  },
  {
    label: 'Mood / Aesthetic',
    options: [
      { value: 'cozy', label: 'Cozy', desc: 'Warm tones, soft textures, hygge mood' },
      { value: 'nature', label: 'Nature', desc: 'Earth tones, botanical, outdoor lighting' },
      { value: 'luxury', label: 'Luxury', desc: 'Premium materials, muted palette, aspirational' },
      { value: 'energetic', label: 'Energetic', desc: 'Motion blur, vibrant colors, high energy' },
      { value: 'nostalgic', label: 'Nostalgic', desc: 'Retro color grading, warm grain, throwback' },
      { value: 'dreamy', label: 'Dreamy', desc: 'Soft focus, pastels, ethereal, light leaks' },
    ],
  },
  {
    label: 'Industry',
    options: [
      { value: 'corporate', label: 'Corporate', desc: 'Even lighting, clean, trustworthy' },
      { value: 'craftsmanship', label: 'Craftsmanship', desc: 'Hands at work, material textures, artisan' },
      { value: 'data-viz', label: 'Data Viz', desc: 'Charts, diagrams, infographic aesthetic' },
      { value: 'ugc', label: 'UGC', desc: 'Phone-camera feel, authentic, no studio' },
    ],
  },
] as const

/** Look up a style's display label by value. */
export function styleLabel(value: string): string {
  for (const g of IMAGE_STYLE_GROUPS) {
    const opt = g.options.find(o => o.value === value)
    if (opt) return opt.label
  }
  return 'Auto'
}
