import { siteConfig } from 'site-config';

const svCategories: { text: string; slug: string }[] = [
  { text: 'Tvättmaskiner',   slug: 'tvattmaskiner' },
  { text: 'Torktumlare',     slug: 'torktumlare' },
  { text: 'Diskmaskiner',    slug: 'diskmaskiner' },
  { text: 'Kylskåp',         slug: 'kylskap' },
  { text: 'Ugnar',           slug: 'ugnar' },
  { text: 'Mikrovågsugnar',  slug: 'mikrovagnsugnar' },
  { text: 'Frysar',          slug: 'frysar' },
];

function categoriesForLocale(locale: string) {
  return locale === 'sv' ? svCategories : siteConfig.categories;
}

export function headerData(locale: string = 'en') {
  const prefix = locale === 'en' ? '' : `/${locale}`;
  return {
    links:
      locale === 'sv'
        ? [
            { text: 'Apparater', href: `${prefix}/` },
            { text: 'Märken', href: `${prefix}/brands/` },
          ]
        : [
            { text: 'Appliances', href: '/' },
            { text: 'Brands', href: '/brands/' },
          ],
    actions: [],
  };
}

export function footerData(locale: string = 'en') {
  const prefix = locale === 'en' ? '' : `/${locale}`;
  const footerCategoryLinks = categoriesForLocale(locale).map((c) => ({
    text: c.text,
    href: `${prefix}/${c.slug}/`,
  }));

  if (locale === 'sv') {
    return {
      links: [
        { title: 'Bläddra', links: footerCategoryLinks },
        {
          title: 'Företag',
          links: [
            { text: 'Om oss', href: `${prefix}/about/` },
            { text: 'Kontakt', href: `${prefix}/contact/` },
            { text: 'Märken', href: `${prefix}/brands/` },
          ],
        },
        {
          title: 'Juridiskt',
          links: [
            { text: 'Integritetspolicy', href: `${prefix}/privacy/` },
            { text: 'Användarvillkor', href: `${prefix}/terms/` },
            { text: 'Cookiepolicy', href: `${prefix}/cookie-policy/` },
            { text: 'Affiliate-information', href: `${prefix}/affiliate-disclosure/` },
            { text: 'Ansvarsfriskrivning', href: `${prefix}/disclaimer/` },
          ],
        },
      ],
      secondaryLinks: [],
      socialLinks: [],
      footNote: `© ${new Date().getFullYear()} ${siteConfig.name}. Alla rättigheter förbehållna.`,
    };
  }

  return {
    links: [
      { title: 'Browse', links: footerCategoryLinks },
      {
        title: 'Company',
        links: [
          { text: 'About', href: '/about/' },
          { text: 'Contact', href: '/contact/' },
          { text: 'Brands', href: '/brands/' },
        ],
      },
      {
        title: 'Legal',
        links: [
          { text: 'Privacy Policy', href: '/privacy/' },
          { text: 'Terms of Service', href: '/terms/' },
          { text: 'Cookie Policy', href: '/cookie-policy/' },
          { text: 'Affiliate Disclosure', href: '/affiliate-disclosure/' },
          { text: 'Disclaimer', href: '/disclaimer/' },
        ],
      },
    ],
    secondaryLinks: [],
    socialLinks: [],
    footNote: `© ${new Date().getFullYear()} ${siteConfig.name}. All rights reserved.`,
  };
}
