FROM node:20-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
EXPOSE 3000
ENV NODE_OPTIONS=--max-old-space-size=512
CMD ["npm", "start"]
