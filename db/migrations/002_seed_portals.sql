-- ============================================================
-- 002_seed_portals.sql
-- Seed all 63 procurement portals
-- ============================================================

-- =========================
-- FEDERAL PORTALS (2)
-- =========================
INSERT INTO portals (name, url, level, province, language, requires_login, enabled) VALUES
('CanadaBuys', 'https://canadabuys.canada.ca/en/tender-opportunities', 'federal', NULL, 'both', false, true),
('MERX', 'https://www.merx.com/', 'federal', NULL, 'both', true, false);

-- =========================
-- PROVINCIAL PORTALS (11)
-- =========================
INSERT INTO portals (name, url, level, province, language, requires_login, enabled) VALUES
('BC Bid', 'https://www.bcbid.gov.bc.ca/', 'provincial', 'British Columbia', 'en', false, true),
('Alberta Purchasing Connection', 'https://vendor.purchasingconnection.ca/', 'provincial', 'Alberta', 'en', true, false),
('SaskTenders', 'https://www.sasktenders.ca/', 'provincial', 'Saskatchewan', 'en', false, true),
('MERX Manitoba', 'https://www.merx.com/mbgov', 'provincial', 'Manitoba', 'en', true, false),
('Ontario Tenders Portal', 'https://ontariotenders.bidsandtenders.ca/', 'provincial', 'Ontario', 'en', false, true),
('SEAO', 'https://www.seao.ca/', 'provincial', 'Quebec', 'fr', true, false),
('New Brunswick Opportunities', 'https://www.gnb.ca/content/gnb/en/departments/finance/procurement.html', 'provincial', 'New Brunswick', 'both', false, true),
('Nova Scotia Procurement', 'https://procurement.novascotia.ca/', 'provincial', 'Nova Scotia', 'en', false, true),
('PEI Procurement', 'https://www.princeedwardisland.ca/en/topic/procurement', 'provincial', 'Prince Edward Island', 'en', false, true),
('Newfoundland Public Procurement', 'https://www.gov.nl.ca/ppa/', 'provincial', 'Newfoundland and Labrador', 'en', false, true),
('Northwest Territories Contract Registry', 'https://contracts.fin.gov.nt.ca/', 'provincial', 'Northwest Territories', 'en', false, true);

-- =========================
-- MUNICIPAL PORTALS (50)
-- =========================
INSERT INTO portals (name, url, level, province, language, requires_login, enabled) VALUES
('Toronto Bids Portal', 'https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/', 'municipal', 'Ontario', 'en', false, true),
('Montreal Tenders', 'https://montreal.ca/en/services/tenders-and-contracts', 'municipal', 'Quebec', 'both', false, true),
('Calgary MERX', 'https://www.calgary.merx.com/', 'municipal', 'Alberta', 'en', true, false),
('Edmonton Procurement', 'https://www.edmonton.ca/business_economy/selling_to_the_city/bid-procurement-opportunities', 'municipal', 'Alberta', 'en', true, false),
('Ottawa MERX', 'https://www.merx.com/cityofottawa', 'municipal', 'Ontario', 'en', true, false),
('Winnipeg MERX', 'https://www.merx.com/mbgov/cityofwinnipeg', 'municipal', 'Manitoba', 'en', true, false),
('Mississauga Bids', 'https://mississauga.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Vancouver Procurement', 'https://vancouver.ca/doing-business/bids-contracts-rfps-and-supplier-portal.aspx', 'municipal', 'British Columbia', 'en', false, true),
('Brampton Bids', 'https://brampton.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Hamilton Bids', 'https://hamilton.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Surrey Bids', 'https://surrey.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Quebec City Procurement', 'https://www.ville.quebec.qc.ca/en/gens_affaires/fournisseur/', 'municipal', 'Quebec', 'both', false, true),
('Halifax Bids', 'https://halifax.bidsandtenders.ca/', 'municipal', 'Nova Scotia', 'en', false, true),
('Laval SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('London Bids', 'https://london.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Markham Bids', 'https://markham.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Vaughan Bids', 'https://vaughan.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Gatineau SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Saskatoon Bids', 'https://saskatoon.bidsandtenders.ca/', 'municipal', 'Saskatchewan', 'en', false, true),
('Kitchener Bids', 'https://kitchener.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Longueuil SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Burnaby Bids', 'https://burnaby.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Windsor Procurement', 'https://www.citywindsor.ca/business/Bids-and-Tenders', 'municipal', 'Ontario', 'en', false, true),
('Regina SaskTenders', 'https://www.sasktenders.ca/', 'municipal', 'Saskatchewan', 'en', false, true),
('Richmond Bids', 'https://richmond.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Richmond Hill Bids', 'https://richmondhill.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Oakville Bids', 'https://oakville.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Burlington Bids', 'https://burlington.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Greater Sudbury Bids', 'https://greatersudbury.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Sherbrooke SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Oshawa Bids', 'https://oshawa.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Saguenay SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Levis SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Barrie Bids', 'https://barrie.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Abbotsford Bids', 'https://abbotsford.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Coquitlam Procurement', 'https://www.coquitlam.ca/140/Bid-Opportunities', 'municipal', 'British Columbia', 'en', false, true),
('Trois-Rivieres SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('St. Catharines Bids', 'https://stcatharines.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Cambridge Procurement', 'https://www.cambridge.ca/en/build-invest-grow/Bids-and-Tenders.aspx', 'municipal', 'Ontario', 'en', false, true),
('Whitby Bids', 'https://whitby.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Guelph Bids', 'https://guelph.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Kingston Procurement', 'https://www.cityofkingston.ca/council-and-city-administration/procurement/', 'municipal', 'Ontario', 'en', false, true),
('Kelowna Procurement', 'https://www.kelowna.ca/business-services/business-city/bidding-opportunities', 'municipal', 'British Columbia', 'en', false, true),
('Moncton Bids', 'https://moncton.bidsandtenders.ca/', 'municipal', 'New Brunswick', 'en', false, true),
('Ajax Bids', 'https://ajax.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Thunder Bay Bids', 'https://thunderbay.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Terrebonne SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('St. Johns Bids', 'https://stjohns.bidsandtenders.ca/', 'municipal', 'Newfoundland and Labrador', 'en', false, true),
('Milton Bids', 'https://milton.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Langley Bids', 'https://tol.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true);
