# Public article pages API

`api_public.article_pages` publishes localized error-code and fault articles.
Article identity is frozen from article type plus the stable public subject ID;
page identity adds locale and is independent of title, slug, and content edits.

Only articles and translations explicitly marked `published` project. A valid
route slug, H1, meta description, active brand/category, and exact localized
category page are mandatory; there is no locale fallback. These gates make
projected pages immediately indexable. Canonical paths preserve the existing
error-code and `/problems/` fault route shapes.

Content JSON and HTML required by the renderer are public, but numeric IDs,
review flags, authors, translation provenance, and internal statuses are not.
The ordinary view is immediately fresh and public roles receive SELECT only.
