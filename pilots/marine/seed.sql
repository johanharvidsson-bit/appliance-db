INSERT INTO locales(code,name,is_active,is_default) VALUES('en','English',true,true)
ON CONFLICT(code) DO UPDATE SET is_active=true,is_default=true;
INSERT INTO categories(slug_en,sort_order,is_active) VALUES
 ('outboard-engines',1,true),('inboard-engines',2,true),('sterndrives',3,true)
ON CONFLICT(slug_en) DO NOTHING;
INSERT INTO category_translations(category_id,locale,name,slug)
SELECT id,'en',CASE slug_en WHEN 'outboard-engines' THEN 'Outboard Engines'
 WHEN 'inboard-engines' THEN 'Inboard Engines' ELSE 'Sterndrives' END,slug_en
FROM categories WHERE slug_en IN('outboard-engines','inboard-engines','sterndrives')
ON CONFLICT(category_id,locale) DO NOTHING;
INSERT INTO brands(name,slug,is_active) VALUES
 ('Mercury','mercury',true),('Yamaha Marine','yamaha-marine',true),('Volvo Penta','volvo-penta',true),
 ('Suzuki Marine','suzuki-marine',true),('Honda Marine','honda-marine',true)
ON CONFLICT(slug) DO NOTHING;
WITH brand_rows AS (
 SELECT id,row_number() OVER(ORDER BY slug) n FROM brands
 WHERE slug IN('mercury','yamaha-marine','volvo-penta','suzuki-marine','honda-marine')
), category_rows AS (
 SELECT id,row_number() OVER(ORDER BY sort_order) n FROM categories
 WHERE slug_en IN('outboard-engines','inboard-engines','sterndrives')
), generated AS (SELECT n FROM generate_series(1,50) n)
INSERT INTO models(brand_id,category_id,name,slug,series,release_year)
SELECT b.id,c.id,'Marine Pilot Model '||g.n,'marine-pilot-model-'||g.n,
       'Pilot '||((g.n-1)/10+1),2020+(g.n%6)
FROM generated g
JOIN brand_rows b ON b.n=((g.n-1)%5)+1
JOIN category_rows c ON c.n=((g.n-1)%3)+1
ON CONFLICT(brand_id,category_id,slug) DO NOTHING;
