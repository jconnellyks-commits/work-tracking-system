-- Add date_given field to advances table
ALTER TABLE advances ADD COLUMN date_given DATE NULL AFTER max_per_period;
