import { vi } from 'vitest'

export const api = {
  listBrands: vi.fn(),
  createBrand: vi.fn(),
  analyzeBrand: vi.fn(),
  getBrand: vi.fn(),
  updateBrand: vi.fn(),
  uploadBrandAsset: vi.fn(),
  deleteBrandAsset: vi.fn(),
  setBrandLogo: vi.fn(),

  listPlans: vi.fn(),
  createPlan: vi.fn(),
  getPlan: vi.fn(),
  updateDay: vi.fn(),

  listPosts: vi.fn(),
  getPost: vi.fn(),
  updatePost: vi.fn(),
  reviewPost: vi.fn(),
  approvePost: vi.fn(),
  exportPost: vi.fn(),
  exportPlan: vi.fn(),

  uploadDayPhoto: vi.fn(),
  deleteDayPhoto: vi.fn(),

  generateVideo: vi.fn(),
  getVideoJob: vi.fn(),

  connectSocial: vi.fn(),

  uploadVideoForRepurpose: vi.fn(),
  getVideoRepurposeJob: vi.fn(),

  downloadCalendar: vi.fn(),
  emailCalendar: vi.fn(),

  getNotionAuthUrl: vi.fn(),
  disconnectNotion: vi.fn(),
  getNotionDatabases: vi.fn(),
  selectNotionDatabase: vi.fn(),
  exportToNotion: vi.fn(),

  editPostMedia: vi.fn(),
  resetPostMedia: vi.fn(),

  regeneratePost: vi.fn(),
  refreshPlanResearch: vi.fn(),
}
