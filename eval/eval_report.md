# Evaluation Results

- Total prompts: 20
- Success rate: 16/20 (80%)
- Avg latency: 110275 ms
- Avg repair rounds triggered: 1.40

| Category | Prompt | Outcome | Repairs | Unresolved | Latency (ms) |
|---|---|---|---|---|---|
| real | Build a CRM with login, contacts, dashboard, role-based acce | success_with_unresolved_repairs | 3 | 1 | 207129.4 |
| real | Create a task management app where users can create projects | success_with_unresolved_repairs | 4 | 1 | 211729.0 |
| real | Build a blog platform where authors can write and publish po | success_with_unresolved_repairs | 3 | 6 | 131824.4 |
| real | I need an inventory management system for a small warehouse: | success_with_unresolved_repairs | 4 | 6 | 264131.6 |
| real | Build a simple booking app for a hair salon: customers book  | success_with_unresolved_repairs | 0 | 42 | 107508.9 |
| real | Create an event ticketing platform: organizers create events | success_clean | 1 | 0 | 101245.0 |
| real | Build a learning management system with courses, lessons, st | success_clean | 0 | 0 | 79620.7 |
| real | I want a real estate listing site: agents post property list | success_with_unresolved_repairs | 3 | 8 | 150028.9 |
| real | Build a freelancer marketplace: freelancers create profiles  | success_with_unresolved_repairs | 3 | 6 | 182408.0 |
| real | Create a gym membership management app: members book classes | success_clean | 1 | 0 | 129197.4 |
| edge_vague | Build me an app. | success_clean | 0 | 0 | 93341.6 |
| edge_vague | I want something like Instagram but better. | success_clean | 0 | 0 | 69985.6 |
| edge_vague | Make a dashboard. | success_with_unresolved_repairs | 3 | 1 | 108245.0 |
| edge_conflicting | Build an app with no login required, but admins need role-ba | exception | 0 | -1 | 75467.5 |
| edge_conflicting | Create a free app with no payment features, but include a pr | success_with_unresolved_repairs | 3 | 1 | 126879.7 |
| edge_conflicting | Build a public app where anyone can view everything, but als | success_clean | 0 | 0 | 53234.9 |
| edge_incomplete | Build a CRM. | success_clean | 0 | 0 | 47293.4 |
| edge_incomplete | I need an app for my business with users and some data. | exception | 0 | -1 | 38428.1 |
| edge_incomplete | Make an app with a dashboard and reports but I'm not sure wh | clarification_needed | 0 | 0 | 20420.7 |
| edge_incomplete | Build something for tracking stuff between team members. | clarification_needed | 0 | 0 | 7380.6 |