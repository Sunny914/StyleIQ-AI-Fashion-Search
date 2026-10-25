import { SearchExperience } from "@/components/SearchExperience";

type SearchPageProps = {
  searchParams: Promise<{ q?: string; gender?: string }>;
};

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  return (
    <section className="page">
      <p className="eyebrow">Search</p>
      <h1>Catalog</h1>
      <SearchExperience query={params.q ?? ""} gender={params.gender ?? ""} />
    </section>
  );
}
