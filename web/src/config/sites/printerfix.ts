export const printerfixConfig = {
  name: 'PrinterFix',
  domain: 'printerfix.com',
  site_id: 2,
  defaultLocale: 'en',
  activeLocales: ['en', 'sv', 'de'],
  colors: {
    primary: '#7c3aed',
    accent: '#16a34a',
    danger: '#dc2626',
  },
  categories: [
    { text: 'Inkjet Printers',  slug: 'inkjet-printers' },
    { text: 'Laser Printers',   slug: 'laser-printers' },
    { text: '3D Printers',      slug: '3d-printers' },
  ],
  // Placeholder slugs - no printerfix DB content exists yet, so these haven't
  // been checked against real category_translations rows.
  categoriesSv: [
    { text: 'Bläckstråleskrivare', slug: 'blackstraleskrivare' },
    { text: 'Laserskrivare',       slug: 'laserskrivare' },
    { text: '3D-skrivare',         slug: '3d-skrivare' },
  ],
  meta: {
    description: 'Fix your printer error codes fast. HP, Epson, Brother and more.',
    twitterHandle: '@printerfix',
    contactEmail: 'info@printerfix.com',
    googleSiteVerificationId: '',
  },
}
