import { getPermalink, getAsset } from './utils/permalinks';
import { siteConfig } from 'site-config';

const categoryLinks = siteConfig.categories.map((c) => ({
  text: c.text,
  href: getPermalink(`/${c.slug}/`),
}))

const footerCategoryLinks = siteConfig.categories.map((c) => ({
  text: c.text,
  href: `/${c.slug}/`,
}))

export const headerData = {
  links: [
    { text: 'Appliances', href: '/' },
    { text: 'Brands', href: '/brands/' },
  ],
  actions: [],
};

export const footerData = {
  links: [
    {
      title: 'Browse',
      links: footerCategoryLinks,
    },
    {
      title: 'Company',
      links: [
        { text: 'About',    href: '/about/' },
        { text: 'Contact',  href: '/contact/' },
        { text: 'Brands',   href: '/brands/' },
      ],
    },
    {
      title: 'Legal',
      links: [
        { text: 'Privacy Policy',      href: '/privacy/' },
        { text: 'Terms of Service',    href: '/terms/' },
        { text: 'Cookie Policy',       href: '/cookie-policy/' },
        { text: 'Affiliate Disclosure', href: '/affiliate-disclosure/' },
        { text: 'Disclaimer',          href: '/disclaimer/' },
      ],
    },
  ],
  secondaryLinks: [],
  socialLinks: [],
  footNote: `© ${new Date().getFullYear()} ${siteConfig.name}. All rights reserved.`,
};
