import { HomeSearch } from "@/components/HomeSearch";

export default function HomePage() {
  return (
    <section className="hero">
      <p className="eyebrow">Fashion discovery</p>
      <h1>Find the piece, not the keyword.</h1>
      <p className="lede">
        Describe a color, a fabric, or a brand. ProductIQ searches the catalog and brings back similar pieces from the same collection.
      </p>
      <HomeSearch />
    </section>
  );
}
