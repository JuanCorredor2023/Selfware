// Mock of what a future PARA endpoint would return: the four PARA
// categories, each with its items. Only "projects" items carry a status.
// Shape per item: { id, name, emailCount, lastActivity, status? }
export const paraTree = [
  {
    key: "projects",
    items: [
      { id: "atlas-hackathon", name: "Atlas / Selfware: Nebius x NVIDIA Hackathon", status: "active", emailCount: 42, lastActivity: "2026-09-29" },
      { id: "thesis", name: "Master's thesis", status: "active", emailCount: 18, lastActivity: "2026-09-24" },
      { id: "year-end-trip", name: "Year-end trip", status: "inactive", emailCount: 5, lastActivity: "2026-07-02" },
    ],
  },
  {
    key: "areas",
    items: [
      { id: "health", name: "Health", emailCount: 14, lastActivity: "2026-09-21" },
      { id: "finances", name: "Personal finances", emailCount: 27, lastActivity: "2026-09-27" },
      { id: "university", name: "University admin", emailCount: 33, lastActivity: "2026-09-26" },
    ],
  },
  {
    key: "resources",
    items: [
      { id: "ml-papers", name: "ML papers and newsletters", emailCount: 61, lastActivity: "2026-09-28" },
      { id: "recipes", name: "Recipes", emailCount: 9, lastActivity: "2026-08-30" },
    ],
  },
  {
    key: "archive",
    items: [
      { id: "summer-internship-2025", name: "Summer internship 2025", emailCount: 37, lastActivity: "2025-09-05" },
      { id: "apartment-2024", name: "Apartment search 2024", emailCount: 22, lastActivity: "2024-12-11" },
    ],
  },
];
