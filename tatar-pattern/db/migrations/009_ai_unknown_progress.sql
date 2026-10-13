-- No fabricated percentage when the cloud has no progress metric.
ALTER TABLE generations ALTER COLUMN progress DROP NOT NULL;
