// Mock of what a future PARA endpoint would return: the four PARA
// categories, each with its items. Only "projects" items carry a status.
// Shape per item: { id, name, email_count, last_activity, status? }
// (the same field names as GET /para in api/app.py)
export const paraTree = [
  {
    key: "projects",
    items: [
      { id: "atlas-hackathon", name: "Atlas / Selfware: Nebius x NVIDIA Hackathon", status: "active", email_count: 42, last_activity: "2026-09-29" },
      { id: "thesis", name: "Master's thesis", status: "active", email_count: 18, last_activity: "2026-09-24" },
      { id: "year-end-trip", name: "Year-end trip", status: "inactive", email_count: 5, last_activity: "2026-07-02" },
    ],
  },
  {
    key: "areas",
    items: [
      { id: "health", name: "Health", email_count: 14, last_activity: "2026-09-21" },
      { id: "finances", name: "Personal finances", email_count: 27, last_activity: "2026-09-27" },
      { id: "university", name: "University admin", email_count: 33, last_activity: "2026-09-26" },
    ],
  },
  {
    key: "resources",
    items: [
      { id: "ml-papers", name: "ML papers and newsletters", email_count: 61, last_activity: "2026-09-28" },
      { id: "recipes", name: "Recipes", email_count: 9, last_activity: "2026-08-30" },
    ],
  },
  {
    key: "archive",
    items: [
      { id: "summer-internship-2025", name: "Summer internship 2025", email_count: 37, last_activity: "2025-09-05" },
      { id: "apartment-2024", name: "Apartment search 2024", email_count: 22, last_activity: "2024-12-11" },
    ],
  },
];
