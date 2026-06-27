import { vi, describe, it, expect, beforeEach } from 'vitest'
import { downloadBlob } from '../../utils/downloads'

describe('downloadBlob', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:mock-url'),
      revokeObjectURL: vi.fn(),
    })
  })

  it('creates an anchor, clicks it, and revokes the object URL', () => {
    const clickSpy = vi.fn()
    const appendSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(node => node)
    const removeSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(node => node)

    const originalCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') {
        const a = originalCreate('a') as HTMLAnchorElement
        a.click = clickSpy
        return a
      }
      return originalCreate(tag)
    })

    const blob = new Blob(['test'])
    downloadBlob(blob, 'test.zip')

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(clickSpy).toHaveBeenCalled()
    expect(appendSpy).toHaveBeenCalled()
    expect(removeSpy).toHaveBeenCalled()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')

    appendSpy.mockRestore()
    removeSpy.mockRestore()
    vi.spyOn(document, 'createElement').mockRestore()
  })

  it('sets correct href and download attributes', () => {
    const anchors: HTMLAnchorElement[] = []
    const originalCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = originalCreate(tag)
      if (tag === 'a') {
        anchors.push(el as HTMLAnchorElement)
        ;(el as HTMLAnchorElement).click = vi.fn()
      }
      return el
    })
    vi.spyOn(document.body, 'appendChild').mockImplementation(node => node)
    vi.spyOn(document.body, 'removeChild').mockImplementation(node => node)

    downloadBlob(new Blob(['x']), 'myfile.csv')

    expect(anchors[0].href).toContain('blob:mock-url')
    expect(anchors[0].download).toBe('myfile.csv')

    vi.spyOn(document, 'createElement').mockRestore()
    vi.spyOn(document.body, 'appendChild').mockRestore()
    vi.spyOn(document.body, 'removeChild').mockRestore()
  })
})
