import { HomeSearch } from "@/components/HomeSearch";

export default function HomePage() {
  return (
    <section className="hero">
      <p className="eyebrow">Fashion discovery</p>
      <h1>Find your style. Beyond the keywords.</h1>
      <p className="lede">
        Discover fashion through meaning, details, and the styles you have in mind.
      </p>
      <HomeSearch />
      <p className="capability-note">
        Search combines keyword overlap with a semantic reading of your description, then returns catalog matches. Category can be limited to Men or Women.
      </p>
    </section>
  );
}
