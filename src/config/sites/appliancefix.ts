export const appliancefixConfig = {
  name: 'Appliance Repair Base',
  domain: 'appliancerepairbase.com',
  site_id: 1,
  defaultLocale: 'en',
  activeLocales: ['en', 'sv'],
  colors: {
    primary: '#2563eb',
    accent: '#16a34a',
    danger: '#dc2626',
  },
  categories: [
    { text: 'Washing Machines', slug: 'washing-machines' },
    { text: 'Dryers',           slug: 'dryers' },
    { text: 'Dishwashers',      slug: 'dishwashers' },
    { text: 'Refrigerators',    slug: 'refrigerators' },
    { text: 'Ovens',            slug: 'ovens' },
    { text: 'Microwaves',       slug: 'microwaves' },
    { text: 'Freezers',         slug: 'freezers' },
  ],
  meta: {
    description:
      'Fix your appliance error codes fast. Step-by-step guides for Samsung, Bosch, LG and more.',
    twitterHandle: '@appliancefix',
    contactEmail: 'info@appliancerepairbase.com',
    googleSiteVerificationId: '',
  },
}
