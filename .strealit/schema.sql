-- schema.sql
DROP TABLE IF EXISTS workout_exercises, workouts, goals, users CASCADE;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    role TEXT DEFAULT 'user'
);

CREATE TABLE goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    exercise TEXT NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min', 'reps', 'weight_lbs', 'distance_mi')),
    target_value NUMERIC NOT NULL,
    target_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    workout_date DATE NOT NULL,
    notes TEXT NOT NULL,
    duration_min INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workout_exercises (
    id SERIAL PRIMARY KEY,
    workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
    exercise TEXT NOT NULL,
    sets INTEGER,
    reps INTEGER,
    weight_lbs NUMERIC,
    time_min NUMERIC,
    rest_min NUMERIC,
    distance_mi NUMERIC
);
