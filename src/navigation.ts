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
    {
      text: 'Browse',
      links: categoryLinks,
    },
  ],
  actions: [],
};

export const footerData = {
  links: [
    {
      title: 'Browse',
      links: footerCategoryLinks,
    },
  ],
  secondaryLinks: [
    { text: 'Terms',          href: getPermalink('/terms') },
    { text: 'Privacy Policy', href: getPermalink('/privacy') },
  ],
  socialLinks: [],
  footNote: `© ${new Date().getFullYear()} ${siteConfig.name}. All rights reserved.`,
};
