import React from 'react';

interface WordmarkProps {
  className?: string;
  as?: React.ElementType;
  'data-testid'?: string;
}

export const Wordmark: React.FC<WordmarkProps> = ({
  className = '',
  as: Component = 'span',
  'data-testid': testId = 'wordmark',
}) => {
  return (
    <Component className={`wordmark ${className}`.trim()} data-testid={testId}>
      <span className="wordmark-interface">INTERFACE</span>
      <span className="wordmark-forge">FORGE</span>
    </Component>
  );
};

export default Wordmark;
