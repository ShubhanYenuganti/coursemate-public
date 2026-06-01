const key = (generationId) => `fc_ratings_${generationId}`;

export function loadRatings(generationId) {
  try {
    return JSON.parse(localStorage.getItem(key(generationId))) ?? {};
  } catch {
    return {};
  }
}

export function setRating(generationId, index, value) {
  const ratings = loadRatings(generationId);
  if (value == null) {
    delete ratings[index];
  } else {
    ratings[index] = value;
  }
  localStorage.setItem(key(generationId), JSON.stringify(ratings));
}
