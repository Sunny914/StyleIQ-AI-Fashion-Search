"use client";

import { useState } from "react";
import type { CategoryGender } from "@/lib/types";

const EXAMPLES = ["navy cotton shirt", "Nike running shoes"];

type SearchFormProps = {
  initialQuery?: string;
  initialGender?: string;
  onSearch: (query: string, gender: CategoryGender | "") => void;
};

export function SearchForm({ initialQuery = "", initialGender = "", onSearch }: SearchFormProps) {
  const [query, setQuery] = useState(initialQuery);
  const [gender, setGender] = useState<CategoryGender | "">(
    initialGender === "Men" || initialGender === "Women" ? initialGender : "",
  );

  function submit(nextQuery: string, nextGender: CategoryGender | "") {
    const trimmed = nextQuery.trim();
    if (!trimmed) {
      return;
    }
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
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Describe a piece, a color, a brand…"
          autoComplete="off"
        />
        <button type="submit">Search</button>
      </div>
      <fieldset className="search-form__filters">
        <legend>Category</legend>
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
      </fieldset>
      <div className="search-form__examples">
        <span>Try</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => {
              setQuery(example);
              submit(example, gender);
            }}
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  );
}
