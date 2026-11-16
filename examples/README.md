# Sample survey

`sample-survey-qualtrics.csv` is a made-up customer survey for a software product, in Qualtrics' export format
(three header rows). Use it to try the plugin or to test a new version before release:

> dig deep into examples/sample-survey-qualtrics.csv

> dig for why small companies are less likely to recommend us, using examples/sample-survey-qualtrics.csv

It has 600 responses from two waves (2026 Q2 and 2026 Q3) and 35 columns: NPS, overall satisfaction, a 7-statement
agreement grid, a select-all features question, a support question asked only of people who contacted support, two
comment boxes, and company size, plan, tenure, role and region.

## What a good report should find

The data was generated with these patterns built in, so you can check the report against them:

| Pattern | Where it should show |
|---|---|
| NPS is slightly below zero (about −7) | Header, Overview |
| Setup, first-month value and value for money drive NPS, and all three are rated poorly ("fix first") | Drivers |
| Reliability is rated well but matters less | Drivers ("nice to have" or "protect") |
| The smaller the company, the lower the NPS (1-10 employees about −50, 1,000+ about +34) | Groups |
| Small companies trail mainly on setup, value for money and first-month value | Groups, two-group comparison |
| Customers of 6-12 months are least happy; setup is their weak spot | Groups (tenure) |
| A large unhappy group, over-represented among 1-10 employee companies, Starter plan and newer customers | Mindsets |
| NPS fell between waves, and the mix shifted (more small companies and newer customers in Q3) | Trend, caveats |
| Comments: setup and price complaints; praise for reliability and support; a few in Spanish, German and French | Comments |
| "How satisfied were you with support?" is asked only of people who contacted support | Data & method (skip logic) |
| 12 speeders removed; emails and IP addresses never shown; the email and phone number in two comments removed | Data & method, quotes |
| Region shows no real differences | Should not be reported as a finding |

Regenerate the file with `python3 examples/make_sample_survey.py`.
