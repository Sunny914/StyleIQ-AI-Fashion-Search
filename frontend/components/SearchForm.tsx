"use client";

import { useState } from "react";
import type { CategoryGender } from "@/lib/types";

const EXAMPLES = [
  "Oversized black cotton shirt",
  "Minimal linen summer outfit",
  "Relaxed-fit denim jacket",
];

type SearchFormProps = {
  initialQuery?: string;
  initialGender?: string;
  pending?: boolean;
  onSearch: (query: string, gender: CategoryGender | "") => void;
};

export function SearchForm({ initialQuery = "", initialGender = "", pending = false, onSearch }: SearchFormProps) {
  const [query, setQuery] = useState(initialQuery);
  const [gender, setGender] = useState<CategoryGender | "">(
    initialGender === "Men" || initialGender === "Women" ? initialGender : "",
  );
  const [hint, setHint] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  function submit(nextQuery: string, nextGender: CategoryGender | "") {
    const trimmed = nextQuery.trim();
    if (!trimmed) {
      setHint("Enter a description to search.");
      return;
    }
    if (pending) {
      return;
    }
    setHint(null);
    onSearch(trimmed, nextGender);
  }

  return (
    <form
      className="search-form"
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        submit(query, gender);
      }}
    >
      <label className="search-form__label" htmlFor="catalog-search">
        Search the catalog
      </label>
      <div className="search-form__row">
        <input
          id="catalog-search"
          name="q"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            if (hint) {
              setHint(null);
            }
          }}
          placeholder="Describe a piece, a color, a fabric, or a brand"
          autoComplete="off"
          enterKeyHint="search"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit(query, gender);
            }
          }}
        />
        {query ? (
          <button
            className="search-form__clear"
            type="button"
            onClick={() => {
              setQuery("");
              setHint(null);
            }}
          >
            Clear
          </button>
        ) : null}
        <button type="submit" disabled={pending || query.trim().length === 0}>
          {pending ? "Searching" : "Search"}
        </button>
      </div>
      {hint ? (
        <p className="search-form__hint" role="status">
          {hint}
        </p>
      ) : null}
      <div className="search-form__tools">
        <button
          className="filter-toggle"
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="category-filters"
          onClick={() => setFiltersOpen((open) => !open)}
        >
          {gender ? `Category: ${gender}` : "Category"}
        </button>
        <div id="category-filters" className={filtersOpen ? "filter-panel-wrap is-open" : "filter-panel-wrap"}>
        <fieldset className="filter-panel">
          <legend>Category</legend>
          <div className="filter-panel__options">
            {(
              [
                ["", "Any"],
                ["Women", "Women"],
                ["Men", "Men"],
              ] as const
            ).map(([value, label]) => (
              <label key={label}>
                <input
                  type="radio"
                  name="category_gender"
                  value={value}
                  checked={gender === value}
                  onChange={() => setGender(value)}
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        </div>
        {gender ? (
          <button className="clear-filter" type="button" onClick={() => setGender("")}>
            Clear category
          </button>
        ) : null}
      </div>
      <div className="search-form__examples">
        <span>Try</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => {
              setQuery(example);
              setHint(null);
            }}
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  );
}
