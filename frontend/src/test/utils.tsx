/* eslint-disable react-refresh/only-export-components */
import React from 'react'
import { MemoryRouter } from 'react-router-dom'

export function RouterWrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

export function createWrapper(initialPath = '/') {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
  }
}
