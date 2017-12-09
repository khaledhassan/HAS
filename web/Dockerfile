FROM node:latest

WORKDIR /app

COPY package.json /app/package.json

RUN npm install

COPY . /app

EXPOSE 3000 8080

CMD ["npm", "run", "start"]

